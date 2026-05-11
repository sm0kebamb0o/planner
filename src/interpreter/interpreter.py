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
from src.interpreter.values import Value, PlannerList, ScaleValue, BracketKind, NIL, T, _is_true
from src.interpreter.signals import PlannerRuntimeError, PlannerFailure, GoSignal, ReturnSignal, ProgStepStatus


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
    # Private methods
    # ------------------------------------------------------------------

    def eval_form(self, node: FormNode) -> Value:  # noqa: C901
        if isinstance(node, IdentNode):
            return node.name

        if isinstance(node, IntNode):
            return node.value

        if isinstance(node, FloatNode):
            return node.value

        if isinstance(node, ScaleNode):
            return ScaleValue(bits=node.bits, source=node.source)

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
                raise PlannerRuntimeError(f"Неизвестный режим переменной: {node.mode}")

            if node.segmented:
                segs = self._segment(val)
                # Кажется имеет смысл переделать логику в этом месте
                # После сегментации атома не должнен получаться список
                # После сегментации списка тоже получается не список :thinking:
                return PlannerList(elements=segs, kind=BracketKind.ROUND)
            return val

        if isinstance(node, LListNode):
            return self._eval_llist(node)

        if isinstance(node, CallNode):
            result = self._eval_call(node.head, node.args)
            if node.segmented:
                segs = self._segment(result)
                return PlannerList(elements=segs, kind=BracketKind.ROUND)
            return result

        raise PlannerRuntimeError(f"Неизвестный тип узла: {type(node)}")


    def _eval_llist(self, node: LListNode) -> PlannerList:
        result: list[Value] = []

        for elem in node.elements:
            if isinstance(elem, VarRefNode) and elem.segmented:
                if elem.mode == VarMode.READ:
                    raw = self.env.get_local(elem.name)
                elif elem.mode == VarMode.CONST:
                    raw = self.env.get_constant(elem.name)
                else:
                    # кажется такое может быть в IS конструкциях
                    raise PlannerRuntimeError("!*X в списке недопустимо")
                result.extend(self._segment(raw))

            elif isinstance(elem, CallNode) and elem.segmented:
                if not elem.args and isinstance(elem.head, IdentNode) and not elem.head.name:
                    pass  # <> — пустой wildcard, не добавляет элементов
                else:
                    raw = self._eval_call(elem.head, elem.args)
                    result.extend(self._segment(raw))

            else:
                result.append(self.eval_form(elem))

        return PlannerList(elements=result, kind=BracketKind.ROUND)

    def _segment(self, val: Value) -> list[Value]:
        if isinstance(val, PlannerList):
            return val.elements
        # Атомы (int, float, str, ScaleValue) — сегмент из одного элемента
        return [val]

    def _eval_call(self, head: FormNode, raw_args: list[FormNode]) -> Value:
        if isinstance(head, IdentNode):
            fn_name: str = head.name
        else:
            head_val = self.eval_form(head)
            if not isinstance(head_val, str):
                raise PlannerRuntimeError(
                    f"Голова вызова должна вычисляться в идентификатор, "
                    f"получено: {self._repr_value(head_val)!r}"
                )
            fn_name = head_val

        # SUBR: аргументы вычисляются заранее
        if fn_name in self._subrs:
            evaled = [self.eval_form(a) for a in raw_args]
            return self._subrs[fn_name](evaled)

        # FSUBR: аргументы НЕ вычисляются
        if fn_name in self._fsubrs:
            return self._fsubrs[fn_name](raw_args)

        # Пока не встретили первую bt функцию, можно выполнять код в нормальном режиме
        if fn_name in self._bt_fsubrs:
            gen = self._bt_fsubrs[fn_name](raw_args)
            try:
                val = next(gen)
                return val
            except StopIteration:
                raise PlannerFailure(message=self._last_failure or NIL)
            # finally:
            #     gen.close()

        # Пользовательская функция
        if fn_name in self._functions:
            return self._call_user_function(self._functions[fn_name], raw_args)

        raise PlannerRuntimeError(f"Неизвестная функция: '{fn_name}'")

    def eval_form_bt(self, node: FormNode) -> Iterator[Value]:
        if isinstance(node, CallNode) and isinstance(node.head, IdentNode):
            fn_name = node.head.name
            if fn_name in self._bt_fsubrs:
                yield from self._bt_fsubrs[fn_name](node.args)
                return
            # Обычный SUBR в BT-режиме: аргументы вычисляются через цепочку
            if fn_name in self._subrs:
                yield from self._eval_subr_bt(fn_name, node.args)
                return

            # Пользовательская функция в BT-режиме
            if fn_name in self._functions:
                yield from self._call_user_function_bt(
                    self._functions[fn_name], node.args
                )
                return

        # Всё остальное: детерминированное вычисление, обёрнутое try/except
        try:
            yield self.eval_form(node)
        except PlannerFailure as f:
            if f.target is not None:
                raise
            self._last_failure = f.message if f.message is not None else NIL

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
                    next_cur, val, status = self._prog_step_back(forks, labels)
                    if status is ProgStepStatus.EXHAUSTED:
                        return
                    if status is ProgStepStatus.RETURN:
                        yield val
                        return
                    cur, last_val = next_cur, val
                    continue

                node = body_nodes[cur]
                if isinstance(node, IdentNode) and node.name in labels:
                    cur += 1
                    continue

                try:
                    gen = self.eval_form_bt(node)
                    val = next(gen)
                except StopIteration:
                    next_cur, val, status = self._prog_step_back(forks, labels)
                    if status is ProgStepStatus.EXHAUSTED:
                        return
                    if status is ProgStepStatus.RETURN:
                        yield val
                        return
                    cur, last_val = next_cur, val
                    continue
                except GoSignal as go:
                    if go.label in labels:
                        cur = labels[go.label]
                        continue
                    self._prog_close_all(forks)
                    raise
                except ReturnSignal as ret:
                    self._prog_close_all(forks)
                    yield ret.value
                    return
                except PlannerFailure as f:
                    if f.target is not None:
                        self._prog_close_all(forks)
                        raise
                    next_cur, val, status = self._prog_step_back(forks, labels)
                    if status is ProgStepStatus.EXHAUSTED:
                        return
                    if status is ProgStepStatus.RETURN:
                        yield val
                        return
                    cur, last_val = next_cur, val
                    continue

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
                try:
                    gen.close()
                except Exception:
                    pass
            except GoSignal as go:
                forks.pop()
                try:
                    gen.close()
                except Exception:
                    pass
                if go.label in labels:
                    return labels[go.label], NIL, ProgStepStatus.GO
                self._prog_close_all(forks)
                raise
            except ReturnSignal as ret:
                self._prog_close_all(forks)
                return -1, ret.value, ProgStepStatus.RETURN
            except PlannerFailure as f:
                forks.pop()
                try:
                    gen.close()
                except Exception:
                    pass
                if f.target is not None:
                    self._prog_close_all(forks)
                    raise
        return -1, NIL, ProgStepStatus.EXHAUSTED

    def _prog_close_all(self, forks: list[tuple[int, Iterator[Value]]]) -> None:
        while forks:
            _, gen = forks.pop()
            try:
                gen.close()
            except Exception:
                pass

    def _call_user_function(
        self, fn: PlannerFunction, raw_args: list[FormNode]
    ) -> Value:
        if isinstance(fn.params, SimpleParam):
            # LAMBDA I или LAMBDA *I
            if fn.params.unevaluated:
                # *I: все аргументы НЕ вычисляются; передаём список AST-узлов
                # (интерпретатор может поже применить EVAL к каждому)
                bound_val: Value = PlannerList(
                    elements=list(raw_args),
                    kind=BracketKind.ROUND,
                )
            else:
                # I: все аргументы вычисляются и собираются в L-список
                bound_val = PlannerList(
                    elements=[self.eval_form(a) for a in raw_args],
                    kind=BracketKind.ROUND,
                )
            declared = [fn.params.name]
            bindings = {fn.params.name: bound_val}

        elif isinstance(fn.params, ListParams):
            # LAMBDA (v1 v2 ...): позиционные параметры
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
            return self.eval_form(fn.body)
        except GoSignal as go:
            raise PlannerRuntimeError(
                f"GO: метка '{go.label}' не определена (выход за границу LAMBDA)"
            )
        finally:
            self.env.pop_frame()

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
            yield from self.eval_form_bt(fn.body)
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
        # Переменная нигде не описана — set_local тоже упадёт; no-op для баланса трейла.
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
