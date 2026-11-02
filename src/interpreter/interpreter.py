from __future__ import annotations

from typing import Callable, Generator

from src.parser.ast.nodes import (
    FormNode, ProgramNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)
from src.interpreter import functions
from src.interpreter.functions import codec
from src.interpreter.trail import Trail
from src.interpreter.database import Database
from src.interpreter.env import Environment, Frame
from src.interpreter.functions import PlannerFunction, SimpleParam, ListParams
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.signals import PlannerFailure
from src.interpreter.control_flow import (
    ControlRequest, ControlExhausted, GoRequest, ReturnRequest, EvalStream,
)
from src.interpreter.values import Value, PlannerList, ScaleValue, BracketKind, NIL, segment_value


class PlannerInterpreter:
    def __init__(self) -> None:
        self.env:            Environment                           = Environment()
        self._functions:     dict[str, PlannerFunction]            = {}
        self._float_digits:  int                                   = 6
        self._subrs:  dict[str, Callable[[list[Value]], Value]]    = {}
        self._trail: Trail = Trail()
        self.database: Database = Database()

        self._last_failure: Value = NIL

        self._bt_fsubrs: dict[str, Callable[[list[FormNode]], EvalStream]] = {}

        self._bt_subrs: dict[str, Callable[[list[Value]], EvalStream]] = {}

        self._matchers: dict[str, Callable[
            [list[FormNode], Value], Generator[ControlRequest, None, bool]
        ]] = {}

        functions.register_all(self)

    # ------------------------------------------------------------------
    # Публичные методы
    # ------------------------------------------------------------------

    def run(self, program: ProgramNode) -> None:
        self._trail.discard_to(0)
        self.database = Database()
        try:
            self._run_program(program)
        finally:
            self._trail.discard_to(0)
            self.database = Database()

    def _run_program(self, program: ProgramNode) -> None:
        for form in program.forms:
            print(codec.repr_form(form))
            try:
                val = self.eval_form(form)
                print(codec.repr_value(val, self._float_digits))
            except PlannerFailure as f:
                msg = f.message if f.message else NIL
                self._last_failure = msg
                print(f"=НЕУСПЕХ= {codec.repr_value(msg, self._float_digits)}")
        
    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def eval_form(self, node: FormNode) -> Value:
        gen = self.eval_form_bt(node)
        try:
            item = next(gen)
            if isinstance(item, ControlRequest):
                raise PlannerRuntimeError("Управляющий запрос достиг границы вычисления")
            return item
        except StopIteration:
            raise PlannerFailure(message=self._last_failure or NIL)
        finally:
            gen.close()

    def eval_first_bt(self, node: FormNode) -> Generator[ControlRequest, None, Value]:
        """Возвращает первое обычное значение и закрывает генератор вычисления формы.

        До получения значения передаёт запросы управления наружу через yield.
        Оставшиеся альтернативы не перебираются; эффекты принятой ветки сохраняются.
        """
        return (yield from self._first_value_bt(self.eval_form_bt(node)))

    def _first_value_bt(self, gen: EvalStream) -> Generator[ControlRequest, None, Value]:
        transferred = False
        try:
            for item in gen:
                if isinstance(item, ControlRequest):
                    transferred = True
                    yield item
                    continue
                return item
            if transferred:
                raise ControlExhausted()
            raise PlannerFailure(message=self._last_failure or NIL)
        finally:
            gen.close()

    def _forward_call_results(self, gen: EvalStream, segmented: bool) -> EvalStream:
        try:
            for item in gen:
                if isinstance(item, ControlRequest):
                    yield item
                elif segmented:
                    yield PlannerList(elements=segment_value(item), kind=BracketKind.ROUND)
                else:
                    yield item
        finally:
            gen.close()

    def _eval_values_bt(self, nodes, index=0, values=(), unevaluated=()) -> Generator[list | ControlRequest, None, None]:
        if index == len(nodes):
            yield list(values)
            return
        if index in unevaluated:
            yield from self._eval_values_bt(nodes, index + 1, values + (nodes[index],), unevaluated)
            return
        gen = self.eval_form_bt(nodes[index])
        try:
            for item in gen:
                if isinstance(item, ControlRequest):
                    yield item
                    continue
                yield from self._eval_values_bt(nodes, index + 1, values + (item,), unevaluated)
        finally:
            gen.close()

    def _eval_llist(self, node: LListNode) -> EvalStream:
        elements = []
        for elem in node.elements:
            if isinstance(elem, VarRefNode) and elem.segmented and elem.mode == VarMode.ASSIGN:
                raise PlannerRuntimeError("!*X в списке недопустимо")
            if (isinstance(elem, CallNode) and elem.segmented and not elem.args
                    and isinstance(elem.head, IdentNode) and not elem.head.name):
                continue
            elements.append(elem)
        gen = self._eval_values_bt(elements)
        try:
            for values in gen:
                if isinstance(values, ControlRequest):
                    yield values
                    continue
                result = []
                for elem, value in zip(elements, values):
                    if isinstance(elem, (VarRefNode, CallNode)) and elem.segmented:
                        result.extend(segment_value(value))
                    else:
                        result.append(value)
                yield PlannerList(elements=result, kind=BracketKind.ROUND)
        finally:
            gen.close()

    def eval_form_bt(self, node: FormNode) -> EvalStream:
        if isinstance(node, CallNode):
            if isinstance(node.head, IdentNode):
                yield from self._eval_call_bt(node.head.name, node)
                return
            head_gen = self.eval_form_bt(node.head)
            try:
                for fn_name in head_gen:
                    if not isinstance(fn_name, str):
                        raise PlannerRuntimeError(
                            f"Голова вызова должна вычисляться в идентификатор, "
                            f"получено: {codec.repr_value(fn_name, self._float_digits)!r}"
                        )
                    yield from self._eval_call_bt(fn_name, node)
            finally:
                head_gen.close()
            return

        if isinstance(node, IdentNode):
            yield node.name
            return

        if isinstance(node, IntNode):
            yield node.value
            return

        if isinstance(node, FloatNode):
            yield node.value
            return

        if isinstance(node, ScaleNode):
            yield ScaleValue(bits=node.bits, source=node.source)
            return

        if isinstance(node, VarRefNode):
            if node.mode == VarMode.READ:
                val = self.env.get_local(node.name)
            elif node.mode == VarMode.CONST:
                val = self.env.get_constant(node.name)
            elif node.mode == VarMode.ASSIGN:
                raise PlannerRuntimeError(
                    f"*{node.name}: обращение с префиксом * используется для записи значения"
                )
            else:
                raise PlannerRuntimeError(
                    f"Неизвестный режим переменной: {node.mode}"
                )
            if node.segmented:
                yield PlannerList(elements=segment_value(val), kind=BracketKind.ROUND)
            else:
                yield val
            return

        if isinstance(node, LListNode):
            yield from self._eval_llist(node)
            return

        raise PlannerRuntimeError(f"Неизвестный тип узла: {type(node)}")

    def _eval_call_bt(self, fn_name: str, node: CallNode) -> EvalStream:
        if fn_name in self._bt_fsubrs:
            try:
                yield from self._forward_call_results(self._bt_fsubrs[fn_name](node.args), node.segmented)
            except ControlExhausted:
                return
            except PlannerFailure as failure:
                if failure.target is not None:
                    raise
                self._last_failure = failure.message if failure.message is not None else NIL
            return

        if fn_name in self._subrs or fn_name in self._bt_subrs:
            yield from self._forward_call_results(self._eval_subr_bt(fn_name, node.args), node.segmented)
            return

        if fn_name in self._functions:
            yield from self._forward_call_results(self._call_user_function_bt(self._functions[fn_name], node.args), node.segmented)
            return

        raise PlannerRuntimeError(f"Неизвестная функция: '{fn_name}'")

    def _eval_subr_bt(
        self, fn_name: str, raw_args: list[FormNode]
    ) -> EvalStream:
        yield from self._eval_subr_args_bt(fn_name, raw_args, 0, [])

    def _eval_subr_args_bt(
        self,
        fn_name: str,
        raw_args: list[FormNode],
        i: int,
        evaled: list[Value],
    ) -> EvalStream:
        if i == len(raw_args):
            mark = self._trail.mark()
            try:
                if fn_name in self._bt_subrs:
                    yield from self._bt_subrs[fn_name](evaled)
                else:
                    yield self._subrs[fn_name](evaled)
                # Когда снова позовем генератор,
                # откатываем побочные эффекты предыдщего вызова
                self._trail.undo_to(mark)
            except PlannerFailure as f:
                self._trail.undo_to(mark)
                if f.target is not None:
                    raise
                self._last_failure = f.message if f.message is not None else NIL
            # Тут неявно вызовется StopIteration из-за чего будет развивать
            # другую "ветку" генераторов
            return
        gen = self.eval_form_bt(raw_args[i])
        try:
            for item in gen:
                if isinstance(item, ControlRequest):
                    yield item
                    continue
                yield from self._eval_subr_args_bt(fn_name, raw_args, i + 1,
                                                   evaled + [item])
        finally:
            gen.close()

    def _eval_body_bt(self, nodes: list[FormNode]) -> EvalStream:
        if not nodes:
            yield NIL
            return
        gen = self.eval_form_bt(nodes[0])
        try:
            for item in gen:
                if isinstance(item, ControlRequest):
                    yield item
                    continue
                if len(nodes) == 1:
                    yield item
                else:
                    yield from self._eval_body_bt(nodes[1:])
        finally:
            gen.close()

    def _eval_prog_bt(
        self,
        declared_names: list[str],
        init_bindings: dict[str, Value],
        labels: dict[str, int],
        body_nodes: list[FormNode],
    ) -> EvalStream:
        frame_index = len(self.env._frames)
        frame = self.env.push_frame(
            declared=declared_names, bindings=init_bindings,
            labels=labels, is_prog=True,
        )
        gen = self._eval_prog_body_bt(frame, body_nodes, 0, NIL)
        try:
            for item in gen:
                if isinstance(item, ControlRequest):
                    yield item
                    continue
                # Скрываем кадры PROG на время выполнения вызывающего кода.
                suspended = self.env._frames[frame_index:]
                del self.env._frames[frame_index:]
                try:
                    yield item
                finally:
                    self.env._frames.extend(suspended)
        finally:
            gen.close()
            self.env.pop_frame()

    def _eval_prog_body_bt(
        self,
        frame: Frame,
        body_nodes: list[FormNode],
        index: int,
        last_val: Value,
    ) -> EvalStream:
        while index < len(body_nodes):
            node = body_nodes[index]
            if not (isinstance(node, IdentNode) and node.name in frame.labels):
                break
            index += 1
        if index == len(body_nodes):
            yield last_val
            return

        gen = self.eval_form_bt(body_nodes[index])
        try:
            for item in gen:
                if isinstance(item, ControlRequest):
                    if item.target is not frame:
                        yield item
                    elif isinstance(item, GoRequest):
                        yield from self._eval_prog_body_bt(frame, body_nodes, item.index, last_val)
                    elif isinstance(item, ReturnRequest):
                        yield item.value
                    else:
                        raise PlannerRuntimeError("Неизвестный управляющий запрос")
                else:
                    yield from self._eval_prog_body_bt(frame, body_nodes, index + 1, item)
        except PlannerFailure as failure:
            if failure.target is not None:
                raise
        finally:
            gen.close()

    def _call_user_function_bt(
        self, fn: PlannerFunction, raw_args: list[FormNode]
    ) -> EvalStream:
        if isinstance(fn.params, SimpleParam):
            declared = [fn.params.name]
            unevaluated = tuple(range(len(raw_args))) if fn.params.unevaluated else ()
        elif isinstance(fn.params, ListParams):
            if len(fn.params.params) != len(raw_args):
                raise PlannerRuntimeError(
                    f"Функция '{fn.name}': ожидалось "
                    f"{len(fn.params.params)} аргументов, получено {len(raw_args)}"
                )
            declared = [name for name, _ in fn.params.params]
            unevaluated = tuple(i for i, (_, raw) in enumerate(fn.params.params) if raw)
        else:
            raise PlannerRuntimeError("Неверная спецификация параметров")
        gen = self._eval_values_bt(raw_args, unevaluated=unevaluated)
        try:
            for values in gen:
                if isinstance(values, ControlRequest):
                    yield values
                    continue
                if isinstance(fn.params, SimpleParam):
                    bindings = {fn.params.name: PlannerList(elements=values, kind=BracketKind.ROUND)}
                else:
                    bindings = dict(zip(declared, values))
                yield from self._call_user_body_bt(fn, declared, bindings)
        finally:
            gen.close()

    def _call_user_body_bt(self, fn, declared, bindings) -> EvalStream:
        frame_index = len(self.env._frames)
        self.env.push_frame(declared, bindings, is_function=True)
        gen = self.eval_form_bt(fn.body)
        try:
            for item in gen:
                if isinstance(item, ControlRequest):
                    yield item
                    continue
                # Скрываем кадр функции на время вычисления соседних аргументов.
                suspended = self.env._frames[frame_index:]
                del self.env._frames[frame_index:]
                try:
                    yield item
                finally:
                    self.env._frames.extend(suspended)
        finally:
            gen.close()
            self.env.pop_frame()

    def _eval_first_args_bt(self, raw_args) -> Generator[ControlRequest, None, list[Value]]:
        values = []
        for node in raw_args:
            values.append((yield from self.eval_first_bt(node)))
        return values

    def _record_undo_local(self, name: str) -> None:
        for frame in reversed(self.env._frames):
            if name in frame.declared:
                if name in frame.bindings:
                    old = frame.bindings[name]
                    self._trail.push_undo(
                        lambda f=frame, n=name, o=old: f.bindings.__setitem__(n, o)
                    )
                else:
                    self._trail.push_undo(
                        lambda f=frame, n=name: f.bindings.pop(n, None)
                    )
                return
        # Переменная нигде не описана
        self._trail.push_undo(lambda: None)

    def _record_undo_constant(self, name: str) -> None:
        if self.env.has_constant(name):
            old = self.env.get_constant(name)
            self._trail.push_undo(
                lambda n=name, o=old: self.env.set_constant(n, o)
            )
        else:
            self._trail.push_undo(
                lambda n=name: self.env._constants.pop(n, None)
            )
