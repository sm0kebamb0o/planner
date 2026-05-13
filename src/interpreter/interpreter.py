from __future__ import annotations

import math
from typing import Callable, Generator, Iterator

from src.parser.ast.nodes import (
    FormNode, ProgramNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)
from src.interpreter import functions
from src.interpreter.functions import codec
from src.interpreter.trail import Trail, _UNBOUND
from src.interpreter.env import Environment
from src.interpreter.functions import PlannerFunction, SimpleParam, ListParams, ParamSpec
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.signals import PlannerFailure, GoSignal, ReturnSignal, ProgStepStatus
from src.interpreter.values import Value, PlannerList, ScaleValue, BracketKind, NIL, T, _is_true


class PlannerInterpreter:
    def __init__(self) -> None:
        self.env:            Environment                           = Environment()
        self._functions:     dict[str, PlannerFunction]            = {}
        self._float_digits:  int                                   = 6
        self._subrs:  dict[str, Callable[[list[Value]], Value]]    = {}
        self._fsubrs: dict[str, Callable[[list[FormNode]], Value]] = {}


        self._trail: Trail = Trail()

        self._last_failure: Value = NIL

        self._bt_fsubrs: dict[str, Callable[[list[FormNode]], Iterator[Value]]] = {}

        self._matchers: dict[str, Callable] = {}

        self._fork_stack: list[Generator] = []

        functions.register_all(self)

        self._read_buffer: list[str] = []   # буфер непрочитанных строк

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def run(self, program: ProgramNode) -> None:
        for form in program.forms:
            print(codec.repr_form(form))
            try:
                val = self.eval_form(form)
                print(self._repr_value(val))
            except PlannerFailure as f:
                msg = f.message if f.message else NIL
                self._last_failure = msg
                print(f"=НЕУСПЕХ= {self._repr_value(msg)}")
            except GoSignal as go:
                raise PlannerRuntimeError(
                    f"GO: метка '{go.label}' не определена"
                )
        
    # ------------------------------------------------------------------
    # Inner methods
    # ------------------------------------------------------------------

    def eval_form(self, node: FormNode) -> Value:
        gen = self.eval_form_bt(node)
        try:
            return next(gen)
        except StopIteration:
            raise PlannerFailure(message=self._last_failure or NIL)
        finally:
            gen.close()

    def _eval_llist(self, node: LListNode) -> PlannerList:
        result: list[Value] = []

        for elem in node.elements:
            if isinstance(elem, VarRefNode) and elem.segmented:
                if elem.mode == VarMode.READ:
                    raw = self.env.get_local(elem.name)
                elif elem.mode == VarMode.CONST:
                    raw = self.env.get_constant(elem.name)
                else:
                    raise PlannerRuntimeError("!*X в списке недопустимо")
                result.extend(self._segment(raw))

            elif isinstance(elem, CallNode) and elem.segmented:
                if (
                    not elem.args
                    and isinstance(elem.head, IdentNode)
                    and not elem.head.name
                ):
                    # <> — пустой wildcard, не добавляет элементов
                    pass
                else:
                    raw = self.eval_form(elem)
                    result.extend(self._segment(raw))

            else:
                result.append(self.eval_form(elem))

        return PlannerList(elements=result, kind=BracketKind.ROUND)

    def _segment(self, val: Value) -> list[Value]:
        if isinstance(val, PlannerList):
            return val.elements
        # Атомы (int, float, str, ScaleValue) — сегмент из одного элемента
        return [val]


    def eval_form_bt(self, node: FormNode) -> Iterator[Value]:
        if isinstance(node, CallNode):
            if isinstance(node.head, IdentNode):
                fn_name = node.head.name
            else:
                fn_name = self.eval_form(node.head)
                if not isinstance(fn_name, str):
                    raise PlannerRuntimeError(
                        f"Голова вызова должна вычисляться в идентификатор, "
                        f"получено: {self._repr_value(fn_name)!r}"
                    )

            if fn_name in self._bt_fsubrs:
                for val in self._bt_fsubrs[fn_name](node.args):
                    if node.segmented:
                        yield PlannerList(elements=self._segment(val), kind=BracketKind.ROUND)
                    else:
                        yield val
                return

            if fn_name in self._subrs:
                for val in self._eval_subr_bt(fn_name, node.args):
                    if node.segmented:
                        yield PlannerList(elements=self._segment(val), kind=BracketKind.ROUND)
                    else:
                        yield val
                return

            if fn_name in self._fsubrs:
                try:
                    result = self._fsubrs[fn_name](node.args)
                    if node.segmented:
                        yield PlannerList(elements=self._segment(result), kind=BracketKind.ROUND)
                    else:
                        yield result
                except PlannerFailure as f:
                    if f.target is not None:
                        raise
                    self._last_failure = f.message if f.message is not None else NIL
                return

            if fn_name in self._functions:
                for val in self._call_user_function_bt(self._functions[fn_name], node.args):
                    if node.segmented:
                        yield PlannerList(elements=self._segment(val), kind=BracketKind.ROUND)
                    else:
                        yield val
                return

            raise PlannerRuntimeError(f"Неизвестная функция: '{fn_name}'")

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
                yield PlannerList(elements=self._segment(val), kind=BracketKind.ROUND)
            else:
                yield val
            return

        if isinstance(node, LListNode):
            yield self._eval_llist(node)
            return

        raise PlannerRuntimeError(f"Неизвестный тип узла: {type(node)}")

    def _eval_subr_bt(
        self, fn_name: str, raw_args: list[FormNode]
    ) -> Iterator[Value]:
        yield from self._eval_subr_args_bt(fn_name, raw_args, 0, [])

    def _eval_subr_args_bt(
        self,
        fn_name: str,
        raw_args: list[FormNode],
        i: int,
        evaled: list[Value],
    ) -> Iterator[Value]:
        if i == len(raw_args):
            mark = self._trail.mark()
            try:
                result = self._subrs[fn_name](evaled)
                yield result
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
        # Для каждого аргумента фактически будет создавать новый генератор
        for arg_val in self.eval_form_bt(raw_args[i]):
            yield from self._eval_subr_args_bt(fn_name, raw_args, i + 1,
                                               evaled + [arg_val])

    def _eval_body_bt(self, nodes: list[FormNode]) -> Iterator[Value]:
        if not nodes:
            yield NIL
            return
        for val in self.eval_form_bt(nodes[0]):
            if len(nodes) == 1:
                yield val
            else:
                yield from self._eval_body_bt(nodes[1:])

    def _eval_prog_bt(
        self,
        declared_names: list[str],
        init_bindings: dict[str, Value],
        labels: dict[str, int],
        body_nodes: list[FormNode],
    ) -> Iterator[Value]:
        self.env.push_frame(
            declared=declared_names,
            bindings=init_bindings,
            labels=labels,
            is_prog=True,
        )
        try:
            forks: list[tuple[int, Iterator[Value]]] = []
            cur: int = 0
            last_val: Value = NIL

            while True:
                if cur >= len(body_nodes):
                    yield last_val
                    while True:
                        next_cur, val, status = self._prog_step_back(forks, labels)
                        if status == ProgStepStatus.EXHAUSTED:
                            return
                        if status == ProgStepStatus.RETURN:
                            yield val
                            continue
                        break
                    cur, last_val = next_cur, val
                    continue

                node = body_nodes[cur]
                if isinstance(node, IdentNode) and node.name in labels:
                    # Наткнулись на метку
                    cur += 1
                    continue

                try:
                    gen = self.eval_form_bt(node)
                    val = next(gen)

                except StopIteration:
                    # Пытаемся продолжить "ветку" которую можем продолжить
                    while True:
                        next_cur, val, status = self._prog_step_back(forks, labels)
                        if status == ProgStepStatus.EXHAUSTED:
                            return
                        if status == ProgStepStatus.RETURN:
                            yield val
                            # Вернемся на предыдущую F-точку
                            continue
                        break
                    cur, last_val = next_cur, val
                    continue

                except GoSignal as go:
                    if go.label in labels:
                        cur = labels[go.label]
                        continue

                    # Не нашли метку в известных
                    self._prog_close_all(forks)
                    raise

                except ReturnSignal as ret:
                    yield ret.value
                    while True:
                        next_cur, val, status = self._prog_step_back(forks, labels)
                        if status == ProgStepStatus.EXHAUSTED:
                            return
                        if status == ProgStepStatus.RETURN:
                            yield val
                            continue
                        break
                    cur, last_val = next_cur, val
                    continue

                except PlannerFailure as f:
                    if f.target is not None:
                        self._prog_close_all(forks)
                        raise
                    while True:
                        next_cur, val, status = self._prog_step_back(forks, labels)
                        if status == ProgStepStatus.EXHAUSTED:
                            # Окажется тут, если не сможем продолжить ни одну "ветку"
                            # Неявно вызовем EXHAUSTED всей prog
                            return
                        if status == ProgStepStatus.RETURN:
                            yield val
                            # Вернемся на предыдущую F-точку
                            continue
                        break
                    cur, last_val = next_cur, val
                    continue
                    
                # Добавляем "метку" (или F-точку), к которой вернемся по FAIL
                forks.append((cur, gen))
                last_val = val
                cur += 1
        finally:
            self.env.pop_frame()

    def _prog_step_back(
        self,
        forks: list[tuple[int, Iterator[Value]]],
        labels: dict[str, int],
    ) -> tuple[int, Value, ProgStepStatus]:
        while forks:
            i, gen = forks[-1]
            try:
                val = next(gen)
                return i + 1, val, ProgStepStatus.OK
            except StopIteration:
                forks.pop()
            except GoSignal as go:
                forks.pop()
                if go.label in labels:
                    return labels[go.label], NIL, ProgStepStatus.GO
                self._prog_close_all(forks)
                raise
            except ReturnSignal as ret:
                forks.pop()
                return -1, ret.value, ProgStepStatus.RETURN
            except PlannerFailure as f:
                forks.pop()
                if f.target is not None:
                    self._prog_close_all(forks)
                    raise
        return -1, NIL, ProgStepStatus.EXHAUSTED

    def _prog_close_all(self, forks: list[tuple[int, Iterator[Value]]]) -> None:
        while forks:
            forks.pop()

    def _call_user_function_bt(
        self, fn: PlannerFunction, raw_args: list[FormNode]
    ) -> Iterator[Value]:
        if isinstance(fn.params, SimpleParam):
            if fn.params.unevaluated:
                bound_val: Value = PlannerList(
                    elements=list(raw_args),
                    kind=BracketKind.ROUND,
                )
            else:
                bound_val = PlannerList(
                    elements=[self.eval_form(a) for a in raw_args],
                    kind=BracketKind.ROUND,
                )
            declared = [fn.params.name]
            bindings = {fn.params.name: bound_val}
        elif isinstance(fn.params, ListParams):
            if len(fn.params.params) != len(raw_args):
                raise PlannerRuntimeError(
                    f"Функция '{fn.name}': ожидалось "
                    f"{len(fn.params.params)} аргументов, "
                    f"получено {len(raw_args)}"
                )
            declared = [name for name, _ in fn.params.params]
            bindings = {}
            for (pname, unevaluated), arg_node in zip(fn.params.params, raw_args):
                if unevaluated:
                    bindings[pname] = arg_node
                else:
                    bindings[pname] = self.eval_form(arg_node)
        else:
            raise PlannerRuntimeError("Неверная спецификация параметров")

        self.env.push_frame(declared, bindings)
        try:
            for val in self.eval_form_bt(fn.body):
                # Снимаем фрейм перед yield чтобы параллельные вычисления
                # аргументов не читали переменные из нашего фрейма
                frame = self.env._frames.pop()
                try:
                    yield val
                finally:
                    self.env._frames.append(frame)
        except GoSignal as go:
            raise PlannerRuntimeError(
                f"GO: метка '{go.label}' не определена (выход за границу LAMBDA)"
            )
        finally:
            self.env.pop_frame()

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

    def _parse_param_spec(self, var_node: FormNode) -> ParamSpec:
        if isinstance(var_node, IdentNode):
            return SimpleParam(name=var_node.name, unevaluated=False)

        if isinstance(var_node, VarRefNode) and var_node.mode == VarMode.ASSIGN:
            return SimpleParam(name=var_node.name, unevaluated=True)

        if isinstance(var_node, LListNode):
            params: list[tuple[str, bool]] = []
            for elem in var_node.elements:
                if isinstance(elem, IdentNode):
                    params.append((elem.name, False))
                elif isinstance(elem, VarRefNode) and elem.mode == VarMode.ASSIGN:
                    params.append((elem.name, True))
                else:
                    raise PlannerRuntimeError(
                        f"LAMBDA: неверная спецификация параметра: {elem!r}"
                    )
            return ListParams(params=params)

        raise PlannerRuntimeError(
            f"LAMBDA: неверная спецификация параметров: {var_node!r}"
        )

    def _check_arity(self, name: str, args: list[Value], expected: int) -> None:
        if len(args) != expected:
            raise PlannerRuntimeError(
                f"{name}: ожидалось {expected} аргументов, получено {len(args)}"
            )

    def _as_number(self, fn: str, val: Value) -> int | float:
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return val
        raise PlannerRuntimeError(
            f"{fn}: ожидалось число, получено {self._repr_value(val)!r}"
        )

    def _as_int(self, fn: str, val: Value) -> int:
        n = self._as_number(fn, val)
        return int(math.floor(float(n) + 0.5))

    def _as_list(self, fn: str, val: Value) -> PlannerList:
        if isinstance(val, PlannerList):
            return val
        raise PlannerRuntimeError(
            f"{fn}: ожидался список, получено {self._repr_value(val)!r}"
        )

    def _as_scale(self, fn: str, val: Value) -> ScaleValue:
        if isinstance(val, ScaleValue):
            return val
        raise PlannerRuntimeError(
            f"{fn}: ожидалась шкала, получено {self._repr_value(val)!r}"
        )

    def _as_ident(self, val: Value) -> str:
        if isinstance(val, str):
            return val
        raise PlannerRuntimeError(
            f"Ожидался идентификатор, получено {self._repr_value(val)!r}"
        )

    def _repr_value(self, val: Value) -> str:
        return codec.repr_value(val, self._float_digits)
