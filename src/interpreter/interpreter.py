from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Union

from src.parser.ast_nodes import (
    FormNode, ProgramNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)


class BracketKind(Enum):
    ROUND  = auto()   # ()  — L-список
    SQUARE = auto()   # []  — P-список
    ANGLE  = auto()   # <>  — S-список


@dataclass
class ScaleValue:
    bits:   int
    source: str

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ScaleValue) and self.bits == other.bits

    def __hash__(self) -> int:
        return hash(self.bits)


@dataclass
class PlannerList:
    elements: list["Value"]
    kind:     BracketKind = BracketKind.ROUND

    def __eq__(self, other: object) -> bool:
        # Два списка равны, если совпадают вид скобок И элементы
        return (
            isinstance(other, PlannerList)
            and self.kind == other.kind
            and self.elements == other.elements
        )

    def __hash__(self) -> int:
        return hash((self.kind, tuple(self.elements)))


Value = Union[int, float, str, ScaleValue, PlannerList]

NIL = PlannerList(elements=[], kind=BracketKind.ROUND)
T   = "T"


def _is_true(val: Value) -> bool:
    """Логическое значение: ложь — только пустой список любого вида."""
    return not (isinstance(val, PlannerList) and len(val.elements) == 0)


class _GoSignal(BaseException):
    """Сигнал перехода по метке ([GO label]).

    Наследован от BaseException (не Exception) чтобы не перехватывался
    левыми 'except Exception:' внутри функций.
    """
    def __init__(self, label: str) -> None:
        self.label = label


class _ReturnSignal(BaseException):
    def __init__(self, value: Value) -> None:
        self.value = value


class PlannerRuntimeError(Exception):
    """Ошибка времени выполнения программы на Плэннере."""


@dataclass
class SimpleParam:
    """LAMBDA I или LAMBDA *I"""
    name:         str
    unevaluated:  bool = False  # Не нужно вычислять аргумент


@dataclass
class ListParams:
    """LAMBDA (v1 v2 ...) — позиционные параметры."""
    params: list[tuple[str, bool]]


ParamSpec = Union[SimpleParam, ListParams]


@dataclass
class PlannerFunction:
    """DEFINE"""
    name:   str
    params: ParamSpec
    body:   FormNode


@dataclass
class Frame:
    """Фрейм стека вызовов

    declared: имена переменных, ОПИСАННЫХ в этом фрейме
    bindings: текущие значения (может не совпадать с declared, если UNASSIGN)
    labels:   метки для GO (только в PROG-фреймах)
    is_prog:  True — фрейм создан PROG (цель для RETURN)
    """
    declared: set[str]           = field(default_factory=set)
    bindings: dict[str, Value]   = field(default_factory=dict)
    labels:   dict[str, int]     = field(default_factory=dict)
    is_prog:  bool               = False


class Environment:
    def __init__(self) -> None:
        self._frames:    list[Frame]       = []
        self._constants: dict[str, Value]  = {}


    def push_frame(
        self,
        declared:  list[str],
        bindings:  dict[str, Value],
        labels:    dict[str, int] | None = None,
        is_prog:   bool = False,
    ) -> Frame:
        frame = Frame(
            declared  = set(declared),
            bindings  = dict(bindings),
            labels    = labels or {},
            is_prog   = is_prog,
        )
        self._frames.append(frame)
        return frame

    def pop_frame(self) -> None:
        if self._frames:
            self._frames.pop()


    def get_local(self, name: str) -> Value:
        """Прочитать значение переменной, поиск сверху вниз."""
        for frame in reversed(self._frames):
            if name in frame.declared:
                if name not in frame.bindings:
                    raise PlannerRuntimeError(
                        f"Переменная '{name}' описана, но не имеет значения"
                    )
                return frame.bindings[name]
        raise PlannerRuntimeError(f"Переменная '{name}' не описана")

    def set_local(self, name: str, value: Value) -> None:
        """Присвоить значение переменной в ближайшем фрейме."""
        for frame in reversed(self._frames):
            if name in frame.declared:
                frame.bindings[name] = value
                return
        raise PlannerRuntimeError(
            f"Попытка присвоить необъявленной переменной '{name}'"
        )

    def is_bound(self, name: str) -> bool:
        """True если имя описано хоть в одном фрейме стека."""
        return any(name in f.declared for f in self._frames)

    def has_value(self, name: str) -> bool:
        """True если описанная переменная имеет текущее значение."""
        for frame in reversed(self._frames):
            if name in frame.declared:
                return name in frame.bindings
        return False

    def unassign(self, name: str) -> None:
        """Удалить значение переменной (UNASSIGN), оставив имя описанным."""
        for frame in reversed(self._frames):
            if name in frame.declared:
                frame.bindings.pop(name, None)
                return
        raise PlannerRuntimeError(f"UNASSIGN: переменная '{name}' не описана")

    def get_constant(self, name: str) -> Value:
        if name not in self._constants:
            raise PlannerRuntimeError(f"Константа '{name}' не определена")
        return self._constants[name]

    def set_constant(self, name: str, value: Value) -> None:
        self._constants[name] = value

    def has_constant(self, name: str) -> bool:
        return name in self._constants


class PlannerInterpreter:
    def __init__(self) -> None:
        self.env:            Environment                           = Environment()
        self._functions:     dict[str, PlannerFunction]            = {}
        self._float_digits:  int                                   = 6
        self._subrs:  dict[str, Callable[[list[Value]], Value]]    = {}
        self._fsubrs: dict[str, Callable[[list[FormNode]], Value]] = {}
        self._build_subr_table()
        self._build_fsubr_table()

        self._read_buffer: list[str] = []   # буфер непрочитанных строк

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def run(self, program: ProgramNode) -> None:
        for form in program.forms:
            print(self._repr_form(form))
            val = self.eval_form(form)
            print(self._repr_value(val))


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
            else:
                # *X в позиции значения — ошибка (только L-value для SET)
                raise PlannerRuntimeError(
                    f"*{node.name}: обращение с префиксом * используется только в SET"
                )

            if node.segmented:
                segs = self._segment(val)
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
                    raise PlannerRuntimeError("!*X в списке недопустимо")
                result.extend(self._segment(raw))

            elif isinstance(elem, CallNode) and elem.segmented:
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

        # Пользовательская функция
        if fn_name in self._functions:
            return self._call_user_function(self._functions[fn_name], raw_args)

        # Сокращение ELEM
        if isinstance(head, (IntNode, FloatNode)):  # float тоже можно
            idx   = self.eval_form(head)
            lst   = self.eval_form(raw_args[0]) if raw_args else NIL
            return self._subr_elem([idx, lst])

        if isinstance(head, VarRefNode) and head.mode in (VarMode.READ, VarMode.CONST):
            idx_val = self.eval_form(head)
            if isinstance(idx_val, (int, float)):
                lst = self.eval_form(raw_args[0]) if raw_args else NIL
                return self._subr_elem([idx_val, lst])

        raise PlannerRuntimeError(f"Неизвестная функция: '{fn_name}'")

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
        finally:
            self.env.pop_frame()

    def _build_fsubr_table(self) -> None:

        fsubrs = self._fsubrs

        def fsubr_or(raw_args: list[FormNode]) -> Value:
            for arg in raw_args:
                val = self.eval_form(arg)
                if _is_true(val):
                    return val
            return NIL

        fsubrs["OR"] = fsubr_or

        def fsubr_and(raw_args: list[FormNode]) -> Value:
            last: Value = T
            for arg in raw_args:
                last = self.eval_form(arg)
                if not _is_true(last):
                    return NIL
            return last

        fsubrs["AND"] = fsubr_and

        def fsubr_cond(raw_args: list[FormNode]) -> Value:
            for clause_node in raw_args:
                if not isinstance(clause_node, LListNode):
                    raise PlannerRuntimeError(
                        f"COND: клауза должна быть списком, получено {clause_node!r}"
                    )
                clause = clause_node.elements
                if not clause:
                    raise PlannerRuntimeError("COND: пустая клауза")

                cond_val = self.eval_form(clause[0])
                if _is_true(cond_val):
                    if len(clause) == 1:
                        return cond_val
                    last: Value = NIL
                    for body_expr in clause[1:]:
                        last = self.eval_form(body_expr)
                    return last

            return NIL

        fsubrs["COND"] = fsubr_cond

        def fsubr_prog(raw_args: list[FormNode]) -> Value:
            if not raw_args:
                raise PlannerRuntimeError("PROG: отсутствует список переменных")

            var_list_node = raw_args[0]
            body_nodes    = raw_args[1:]

            if not isinstance(var_list_node, LListNode):
                raise PlannerRuntimeError(
                    "PROG: первый аргумент должен быть L-списком переменных"
                )

            declared_names: list[str]        = []
            init_bindings:  dict[str, Value] = {}

            for decl in var_list_node.elements:
                if isinstance(decl, IdentNode):
                    declared_names.append(decl.name)
                elif isinstance(decl, LListNode) and len(decl.elements) == 2:
                    name_node = decl.elements[0]
                    if not isinstance(name_node, IdentNode):
                        raise PlannerRuntimeError(
                            f"PROG: имя переменной должно быть идентификатором, "
                            f"получено {name_node!r}"
                        )
                    declared_names.append(name_node.name)
                    init_bindings[name_node.name] = self.eval_form(decl.elements[1])
                else:
                    raise PlannerRuntimeError(
                        f"PROG: неверное объявление переменной: {decl!r}"
                    )

            labels: dict[str, int] = {}
            for i, node in enumerate(body_nodes):
                if isinstance(node, IdentNode):
                    labels[node.name] = i

            self.env.push_frame(
                declared=declared_names,
                bindings=init_bindings,
                labels=labels,
                is_prog=True,
            )
            try:
                last_val: Value = NIL
                i = 0
                while i < len(body_nodes):
                    node = body_nodes[i]

                    if isinstance(node, IdentNode) and node.name in labels:
                        i += 1
                        continue

                    try:
                        last_val = self.eval_form(node)
                    except _GoSignal as go:
                        if go.label in labels:
                            i = labels[go.label]
                            continue
                        raise

                    i += 1

                return last_val

            except _ReturnSignal as ret:
                return ret.value
            finally:
                self.env.pop_frame()

        fsubrs["PROG"] = fsubr_prog

        def fsubr_do(raw_args: list[FormNode]) -> Value:
            last: Value = NIL
            for arg in raw_args:
                last = self.eval_form(arg)
            return last

        fsubrs["DO"] = fsubr_do

        def fsubr_loop(raw_args: list[FormNode]) -> Value:
            if len(raw_args) < 2:
                raise PlannerRuntimeError("LOOP: нужны x, l и тело")

            param_node = raw_args[0]
            if not isinstance(param_node, IdentNode):
                raise PlannerRuntimeError(
                    "LOOP: первый аргумент должен быть именем переменной"
                )
            param_name = param_node.name
            body_nodes = raw_args[2:]

            lst = self.eval_form(raw_args[1])
            if not isinstance(lst, PlannerList):
                raise PlannerRuntimeError("LOOP: второй аргумент должен быть списком")

            if not lst.elements:
                return NIL

            self.env.push_frame([param_name], {})
            try:
                last_val: Value = NIL
                for elem in lst.elements:
                    self.env.set_local(param_name, elem)
                    for body_expr in body_nodes:
                        last_val = self.eval_form(body_expr)
                return last_val
            finally:
                self.env.pop_frame()

        fsubrs["LOOP"] = fsubr_loop

        def fsubr_for(raw_args: list[FormNode]) -> Value:
            if len(raw_args) < 2:
                raise PlannerRuntimeError("FOR: нужны x, n и тело")

            param_node = raw_args[0]
            if not isinstance(param_node, IdentNode):
                raise PlannerRuntimeError(
                    "FOR: первый аргумент должен быть именем переменной"
                )
            param_name = param_node.name
            body_nodes = raw_args[2:]

            n_val = self.eval_form(raw_args[1])
            if not isinstance(n_val, (int, float)):
                raise PlannerRuntimeError("FOR: второй аргумент должен быть числом")
            n = int(round(n_val))

            if n < 1:
                return NIL

            self.env.push_frame([param_name], {})
            try:
                last_val: Value = NIL
                for i in range(1, n + 1):
                    self.env.set_local(param_name, i)
                    for body_expr in body_nodes:
                        last_val = self.eval_form(body_expr)
                return last_val
            finally:
                self.env.pop_frame()

        fsubrs["FOR"] = fsubr_for

        def fsubr_while(raw_args: list[FormNode]) -> Value:
            if not raw_args:
                raise PlannerRuntimeError("WHILE: нужны условие и тело")

            pred_node  = raw_args[0]
            body_nodes = raw_args[1:]

            while _is_true(self.eval_form(pred_node)):
                for body_expr in body_nodes:
                    self.eval_form(body_expr)

            return NIL

        fsubrs["WHILE"] = fsubr_while

        def fsubr_until(raw_args: list[FormNode]) -> Value:
            if not raw_args:
                raise PlannerRuntimeError("UNTIL: нужны тело и условие")

            body_nodes = raw_args[:-1]
            pred_node  = raw_args[-1]

            while True:
                for body_expr in body_nodes:
                    self.eval_form(body_expr)
                if _is_true(self.eval_form(pred_node)):
                    break

            return NIL

        fsubrs["UNTIL"] = fsubr_until

        def fsubr_define(raw_args: list[FormNode]) -> Value:
            if len(raw_args) != 2:
                raise PlannerRuntimeError(
                    "DEFINE: ожидается ровно два аргумента: имя и LAMBDA-выражение"
                )

            fn_name_node = raw_args[0]
            if not isinstance(fn_name_node, IdentNode):
                raise PlannerRuntimeError(
                    "DEFINE: первый аргумент должен быть идентификатором"
                )
            fn_name = fn_name_node.name

            lambda_node = raw_args[1]
            if not isinstance(lambda_node, LListNode) or len(lambda_node.elements) != 3:
                raise PlannerRuntimeError(
                    "DEFINE: второй аргумент должен быть (LAMBDA var body)"
                )

            keyword, var_node, body_node = lambda_node.elements
            if not isinstance(keyword, IdentNode) or keyword.name != "LAMBDA":
                raise PlannerRuntimeError(
                    "DEFINE: ожидается ключевое слово LAMBDA"
                )

            params = self._parse_param_spec(var_node)

            self._functions[fn_name] = PlannerFunction(
                name   = fn_name,
                params = params,
                body   = body_node,
            )
            return fn_name

        fsubrs["DEFINE"] = fsubr_define

        def fsubr_quote(raw_args: list[FormNode]) -> Value:
            if len(raw_args) != 1:
                raise PlannerRuntimeError("QUOTE: ожидается ровно один аргумент")
            return self._ast_to_value(raw_args[0])

        fsubrs["QUOTE"] = fsubr_quote

        def fsubr_form(raw_args: list[FormNode]) -> Value:
            result: list[Value] = []
            for arg in raw_args:
                if isinstance(arg, VarRefNode) and arg.segmented:
                    raw_v = (self.env.get_local(arg.name) if arg.mode == VarMode.READ
                             else self.env.get_constant(arg.name))
                    result.extend(self._segment(raw_v))
                elif isinstance(arg, CallNode) and arg.segmented:
                    raw_v = self._eval_call(arg.head, arg.args)
                    result.extend(self._segment(raw_v))
                else:
                    result.append(self.eval_form(arg))
            return PlannerList(elements=result, kind=BracketKind.ROUND)

        fsubrs["FORM"] = fsubr_form

    def _build_subr_table(self) -> None:
        """Зарегистрировать все SUBR-функции."""

        subrs = self._subrs

        def subr_elem(args: list[Value]) -> Value:
            self._check_arity("ELEM", args, 2)
            n = self._as_int("ELEM", args[0])
            lst = self._as_list("ELEM", args[1])
            ln = len(lst.elements)
            if n == 0 or abs(n) > ln:
                raise PlannerRuntimeError(
                    f"ELEM: индекс {n} за пределами списка длины {ln}"
                )
            idx = (n - 1) if n > 0 else (ln + n)
            return lst.elements[idx]

        subrs["ELEM"] = subr_elem
        self._subr_elem = subr_elem

        def subr_index(args: list[Value]) -> Value:
            if len(args) < 2:
                raise PlannerRuntimeError("INDEX: нужны список и хотя бы один индекс")
            result: Value = args[0]
            for n_val in args[1:]:
                result = subr_elem([n_val, result])
            return result

        subrs["INDEX"] = subr_index

        def subr_rest(args: list[Value]) -> Value:
            self._check_arity("REST", args, 2)
            n   = self._as_int("REST", args[0])
            lst = self._as_list("REST", args[1])
            ln  = len(lst.elements)
            if abs(n) > ln:
                raise PlannerRuntimeError(
                    f"REST: |n|={abs(n)} превышает длину списка {ln}"
                )
            if n >= 0:
                new_elems = lst.elements[n:]
            else:
                new_elems = lst.elements[:ln + n]
            return PlannerList(elements=new_elems, kind=lst.kind)

        subrs["REST"] = subr_rest

        def subr_head(args: list[Value]) -> Value:
            self._check_arity("HEAD", args, 2)
            n   = self._as_int("HEAD", args[0])
            lst = self._as_list("HEAD", args[1])
            ln  = len(lst.elements)
            if abs(n) > ln:
                raise PlannerRuntimeError(
                    f"HEAD: |n|={abs(n)} превышает длину списка {ln}"
                )
            if n >= 0:
                new_elems = lst.elements[:n]
            else:
                new_elems = lst.elements[ln + n:]
            return PlannerList(elements=new_elems, kind=lst.kind)

        subrs["HEAD"] = subr_head

        def subr_length(args: list[Value]) -> Value:
            self._check_arity("LENGTH", args, 1)
            lst = self._as_list("LENGTH", args[0])
            return len(lst.elements)

        subrs["LENGTH"] = subr_length

        def subr_add(args: list[Value]) -> Value:
            if not args:
                raise PlannerRuntimeError("+: нужен хотя бы один аргумент")
            total: int | float = 0
            for a in args:
                total = total + self._as_number("+", a)
            return total

        subrs["+"] = subr_add

        def subr_sub(args: list[Value]) -> Value:
            self._check_arity("-", args, 2)
            return self._as_number("-", args[0]) - self._as_number("-", args[1])

        subrs["-"] = subr_sub

        def subr_mul(args: list[Value]) -> Value:
            if not args:
                raise PlannerRuntimeError("×: нужен хотя бы один аргумент")
            result: int | float = 1
            for a in args:
                result = result * self._as_number("×", a)
            return result

        subrs["×"] = subr_mul
        subrs["*"] = subr_mul

        def subr_div(args: list[Value]) -> Value:
            self._check_arity("/", args, 2)
            n2 = self._as_number("/", args[1])
            if n2 == 0:
                raise PlannerRuntimeError("/: деление на ноль")
            return float(self._as_number("/", args[0])) / float(n2)

        subrs["/"] = subr_div

        def subr_idiv(args: list[Value]) -> Value:
            self._check_arity("DIV", args, 2)
            n1 = self._as_number("DIV", args[0])
            n2 = self._as_number("DIV", args[1])
            if n2 == 0:
                raise PlannerRuntimeError("DIV: деление на ноль")
            return int(math.floor(n1 / n2))

        subrs["DIV"] = subr_idiv

        def subr_mod(args: list[Value]) -> Value:
            self._check_arity("MOD", args, 2)
            n1 = self._as_number("MOD", args[0])
            n2 = self._as_number("MOD", args[1])
            if n2 == 0:
                raise PlannerRuntimeError("MOD: деление на ноль")
            return n1 - n2 * math.floor(n1 / n2)

        subrs["MOD"] = subr_mod

        def subr_pow(args: list[Value]) -> Value:
            self._check_arity("↑", args, 2)
            base = self._as_number("↑", args[0])
            exp  = self._as_number("↑", args[1])
            result = base ** exp
            # Целый результат если оба целых и exp >= 0
            if isinstance(base, int) and isinstance(exp, int) and exp >= 0:
                return int(result)
            return float(result)

        subrs["↑"] = subr_pow

        for fn_name, fn_impl in [
            ("ABS",    lambda x: abs(x)),
            ("ENTIER", lambda x: int(math.floor(x))),
            ("ROUND",  lambda x: int(math.floor(x + 0.5))),
            ("SIGN",   lambda x: 1 if x > 0 else (0 if x == 0 else -1)),
            ("SQRT",   lambda x: math.sqrt(x)),
            ("SIN",    lambda x: math.sin(x)),
            ("COS",    lambda x: math.cos(x)),
            ("TG",     lambda x: math.tan(x)),
            ("CTG",    lambda x: 1.0 / math.tan(x)),
            ("ARCSIN", lambda x: math.asin(x)),
            ("ARCCOS", lambda x: math.acos(x)),
            ("ARCTG",  lambda x: math.atan(x)),
            ("EXP",    lambda x: math.exp(x)),
            ("LN",     lambda x: math.log(x)),
        ]:
            def _make_math_subr(name: str, impl: Callable) -> Callable:
                def _fn(args: list[Value], _name=name, _impl=impl) -> Value:
                    self._check_arity(_name, args, 1)
                    x = self._as_number(_name, args[0])
                    return _impl(float(x))
                return _fn
            subrs[fn_name] = _make_math_subr(fn_name, fn_impl)

        def subr_max(args: list[Value]) -> Value:
            if not args:
                raise PlannerRuntimeError("MAX: нужен хотя бы один аргумент")
            nums = [self._as_number("MAX", a) for a in args]
            return max(nums)

        subrs["MAX"] = subr_max

        def subr_min(args: list[Value]) -> Value:
            if not args:
                raise PlannerRuntimeError("MIN: нужен хотя бы один аргумент")
            nums = [self._as_number("MIN", a) for a in args]
            return min(nums)

        subrs["MIN"] = subr_min

        def subr_random(args: list[Value]) -> Value:
            import random
            return random.random()

        subrs["RANDOM"] = subr_random

        def subr_bitor(args: list[Value]) -> Value:
            self._check_arity("\\/", args, 2)
            s1, s2 = self._as_scale("\\/", args[0]), self._as_scale("\\/", args[1])
            result_bits = s1.bits | s2.bits
            return ScaleValue(bits=result_bits, source=oct(result_bits)[2:])

        subrs["\\/"] = subr_bitor

        def subr_bitand(args: list[Value]) -> Value:
            self._check_arity("/\\", args, 2)
            s1, s2 = self._as_scale("/\\", args[0]), self._as_scale("/\\", args[1])
            result_bits = s1.bits & s2.bits
            return ScaleValue(bits=result_bits, source=oct(result_bits)[2:])

        subrs["/\\"] = subr_bitand

        def subr_comp(args: list[Value]) -> Value:
            self._check_arity("COMP", args, 2)
            s1, s2 = self._as_scale("COMP", args[0]), self._as_scale("COMP", args[1])
            result_bits = s1.bits ^ s2.bits
            return ScaleValue(bits=result_bits, source=oct(result_bits)[2:])

        subrs["COMP"] = subr_comp

        def subr_shift(args: list[Value]) -> Value:
            self._check_arity("SHIFT", args, 2)
            s = self._as_scale("SHIFT", args[0])
            n = self._as_int("SHIFT", args[1])
            if n >= 0:
                result_bits = s.bits >> n
            else:
                result_bits = s.bits << (-n)
            return ScaleValue(bits=result_bits, source=oct(result_bits)[2:])

        subrs["SHIFT"] = subr_shift

        def subr_bsum(args: list[Value]) -> Value:
            self._check_arity("BSUM", args, 1)
            s = self._as_scale("BSUM", args[0])
            return bin(s.bits).count("1")

        subrs["BSUM"] = subr_bsum

        def subr_topbit(args: list[Value]) -> Value:
            self._check_arity("TOPBIT", args, 1)
            s = self._as_scale("TOPBIT", args[0])
            return s.bits.bit_length()   # 0 если нет единиц

        subrs["TOPBIT"] = subr_topbit

        def _bool(cond: bool) -> Value:
            return T if cond else NIL

        subrs["ID"]     = lambda a: _bool(len(a) == 1 and isinstance(a[0], str))
        subrs["NUM"]    = lambda a: _bool(len(a) == 1 and isinstance(a[0], (int, float)) and not isinstance(a[0], bool))
        subrs["INT"]    = lambda a: _bool(len(a) == 1 and isinstance(a[0], int) and not isinstance(a[0], bool))
        subrs["REAL"]   = lambda a: _bool(len(a) == 1 and isinstance(a[0], float))
        subrs["SCALE"]  = lambda a: _bool(len(a) == 1 and isinstance(a[0], ScaleValue))
        subrs["ATOM"]   = lambda a: _bool(len(a) == 1 and not isinstance(a[0], PlannerList))
        subrs["ATOMIC"] = subrs["ATOM"]
        subrs["LIST"]   = lambda a: _bool(len(a) == 1 and isinstance(a[0], PlannerList) and a[0].kind == BracketKind.ROUND)
        subrs["LISTR"]  = lambda a: _bool(len(a) == 1 and isinstance(a[0], PlannerList))
        subrs["LISTP"]  = lambda a: _bool(len(a) == 1 and isinstance(a[0], PlannerList) and a[0].kind == BracketKind.SQUARE)
        subrs["LISTS"]  = lambda a: _bool(len(a) == 1 and isinstance(a[0], PlannerList) and a[0].kind == BracketKind.ANGLE)
        subrs["EMPTY"]  = lambda a: _bool(len(a) == 1 and isinstance(a[0], PlannerList) and len(a[0].elements) == 0)
        # VAR: всегда ложь для вычисленного значения (VarRef уже разыменован)
        subrs["VAR"]    = lambda a: NIL

        subrs["EQ"]  = lambda a: _bool(len(a) == 2 and a[0] == a[1])
        subrs["NEQ"] = lambda a: _bool(len(a) == 2 and a[0] != a[1])
        subrs["GT"]  = lambda a: _bool(len(a) == 2 and self._as_number("GT",  a[0]) >  self._as_number("GT",  a[1]))
        subrs["GE"]  = lambda a: _bool(len(a) == 2 and self._as_number("GE",  a[0]) >= self._as_number("GE",  a[1]))
        subrs["LT"]  = lambda a: _bool(len(a) == 2 and self._as_number("LT",  a[0]) <  self._as_number("LT",  a[1]))
        subrs["LE"]  = lambda a: _bool(len(a) == 2 and self._as_number("LE",  a[0]) <= self._as_number("LE",  a[1]))

        def subr_memb(args: list[Value]) -> Value:
            self._check_arity("MEMB", args, 2)
            e   = args[0]
            lst = self._as_list("MEMB", args[1])
            for i, elem in enumerate(lst.elements, start=1):
                if elem == e:
                    return i
            return NIL

        subrs["MEMB"] = subr_memb

        subrs["NOT"] = lambda a: (T if not _is_true(a[0]) else NIL) if len(a) == 1 else NIL

        def subr_set(args: list[Value]) -> Value:
            self._check_arity("SET", args, 2)
            name = args[0]
            if not isinstance(name, str):
                raise PlannerRuntimeError(
                    f"SET: первый аргумент должен быть именем переменной, "
                    f"получено {self._repr_value(name)!r}"
                )
            self.env.set_local(name, args[1])
            return args[1]

        subrs["SET"] = subr_set

        def subr_go(args: list[Value]) -> Value:
            self._check_arity("GO", args, 1)
            label = args[0]
            if not isinstance(label, str):
                raise PlannerRuntimeError("GO: аргумент должен быть идентификатором")
            raise _GoSignal(label)

        subrs["GO"] = subr_go

        def subr_return(args: list[Value]) -> Value:
            self._check_arity("RETURN", args, 1)
            raise _ReturnSignal(args[0])

        subrs["RETURN"] = subr_return

        def subr_fin(args: list[Value]) -> Value:
            self._check_arity("FIN", args, 2)
            i1 = args[0]
            i2 = args[1]
            if not isinstance(i1, str) or not isinstance(i2, str):
                raise PlannerRuntimeError("FIN: аргументы должны быть именами переменных")
            lst = self.env.get_local(i2)
            if isinstance(lst, PlannerList) and lst.elements:
                self.env.set_local(i1, lst.elements[0])
                self.env.set_local(i2, PlannerList(
                    elements=lst.elements[1:], kind=lst.kind
                ))
                return NIL
            return T

        subrs["FIN"] = subr_fin

        def subr_add1(args: list[Value]) -> Value:
            self._check_arity("ADD1", args, 1)
            name = args[0]
            if not isinstance(name, str):
                raise PlannerRuntimeError("ADD1: аргумент должен быть именем переменной")
            val = self.env.get_local(name)
            new_val = self._as_number("ADD1", val) + 1
            new_val = int(new_val) if isinstance(val, int) else float(new_val)
            self.env.set_local(name, new_val)
            return new_val

        subrs["ADD1"] = subr_add1

        def subr_sub1(args: list[Value]) -> Value:
            self._check_arity("SUB1", args, 1)
            name = args[0]
            if not isinstance(name, str):
                raise PlannerRuntimeError("SUB1: аргумент должен быть именем переменной")
            val = self.env.get_local(name)
            new_val = self._as_number("SUB1", val) - 1
            new_val = int(new_val) if isinstance(val, int) else float(new_val)
            self.env.set_local(name, new_val)
            return new_val

        subrs["SUB1"] = subr_sub1

        def subr_bound(args: list[Value]) -> Value:
            self._check_arity("BOUND", args, 1)
            if not isinstance(args[0], str):
                raise PlannerRuntimeError("BOUND: аргумент должен быть именем")
            return T if self.env.is_bound(args[0]) else NIL

        subrs["BOUND"] = subr_bound

        def subr_hasval(args: list[Value]) -> Value:
            self._check_arity("HASVAL", args, 1)
            if not isinstance(args[0], str):
                raise PlannerRuntimeError("HASVAL: аргумент должен быть именем")
            return T if self.env.has_value(args[0]) else NIL

        subrs["HASVAL"] = subr_hasval

        def subr_unassign(args: list[Value]) -> Value:
            self._check_arity("UNASSIGN", args, 1)
            if not isinstance(args[0], str):
                raise PlannerRuntimeError("UNASSIGN: аргумент должен быть именем")
            self.env.unassign(args[0])
            return args[0]

        subrs["UNASSIGN"] = subr_unassign

        def subr_value(args: list[Value]) -> Value:
            self._check_arity("VALUE", args, 1)
            if not isinstance(args[0], str):
                raise PlannerRuntimeError("VALUE: аргумент должен быть именем переменной")
            return self.env.get_local(args[0])

        subrs["VALUE"] = subr_value

        def subr_cset(args: list[Value]) -> Value:
            self._check_arity("CSET", args, 2)
            if not isinstance(args[0], str):
                raise PlannerRuntimeError("CSET: первый аргумент должен быть именем")
            self.env.set_constant(args[0], args[1])
            return args[1]

        subrs["CSET"] = subr_cset

        def subr_print(args: list[Value]) -> Value:
            self._check_arity("PRINT", args, 1)
            print(self._repr_value(args[0]))
            return args[0]

        subrs["PRINT"] = subr_print

        def subr_mprint(args: list[Value]) -> Value:
            print(" ".join(self._repr_value(a) for a in args))
            return PlannerList(elements=list(args), kind=BracketKind.ROUND)

        subrs["MPRINT"] = subr_mprint

        def subr_digits(args: list[Value]) -> Value:
            if not args:
                return self._float_digits
            n = self._as_int("DIGITS", args[0])
            if n < 0:
                raise PlannerRuntimeError("DIGITS: число цифр не может быть отрицательным")
            self._float_digits = n
            return n

        subrs["DIGITS"] = subr_digits

        def subr_eval(args: list[Value]) -> Value:
            self._check_arity("EVAL", args, 1)
            ast_node = self._value_to_form(args[0])
            return self.eval_form(ast_node)

        subrs["EVAL"] = subr_eval

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

    def _ast_to_value(self, node: FormNode) -> Value:
        if isinstance(node, IdentNode):
            return node.name
        if isinstance(node, IntNode):
            return node.value
        if isinstance(node, FloatNode):
            return node.value
        if isinstance(node, ScaleNode):
            return ScaleValue(bits=node.bits, source=node.source)
        if isinstance(node, VarRefNode):
            prefix = {
                (VarMode.READ,   False): ".",
                (VarMode.ASSIGN, False): "*",
                (VarMode.CONST,  False): ":",
                (VarMode.READ,   True):  "!.",
                (VarMode.ASSIGN, True):  "!*",
                (VarMode.CONST,  True):  "!:",
            }[(node.mode, node.segmented)]
            return PlannerList(
                elements=[prefix + node.name],
                kind=BracketKind.ROUND
            )
        if isinstance(node, LListNode):
            return PlannerList(
                elements=[self._ast_to_value(e) for e in node.elements],
                kind=BracketKind.ROUND,
            )
        if isinstance(node, CallNode):
            kind = BracketKind.ANGLE if node.segmented else BracketKind.SQUARE
            elems = [self._ast_to_value(node.head)] + [
                self._ast_to_value(a) for a in node.args
            ]
            return PlannerList(elements=elems, kind=kind)
        raise PlannerRuntimeError(f"_ast_to_value: неизвестный тип {type(node)}")

    def _value_to_form(self, val: Value) -> FormNode:
        if isinstance(val, str):
            return IdentNode(name=val)
        if isinstance(val, int):
            return IntNode(value=val)
        if isinstance(val, float):
            return FloatNode(value=val)
        if isinstance(val, ScaleValue):
            return ScaleNode(bits=val.bits, source=val.source)
        if isinstance(val, PlannerList):
            if val.kind == BracketKind.SQUARE and val.elements:
                head_node = self._value_to_form(val.elements[0])
                arg_nodes = [self._value_to_form(e) for e in val.elements[1:]]
                return CallNode(head=head_node, args=arg_nodes, segmented=False)
            if val.kind == BracketKind.ANGLE and val.elements:
                head_node = self._value_to_form(val.elements[0])
                arg_nodes = [self._value_to_form(e) for e in val.elements[1:]]
                return CallNode(head=head_node, args=arg_nodes, segmented=True)
            return LListNode(elements=[self._value_to_form(e) for e in val.elements])
        raise PlannerRuntimeError(
            f"_value_to_form: нельзя конвертировать {type(val)} в форму"
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
        if val is NIL or (isinstance(val, PlannerList) and not val.elements):
            return "()"
        if isinstance(val, str):
            return val
        if isinstance(val, bool):
            return "T" if val else "()"
        if isinstance(val, int):
            return str(val)
        if isinstance(val, float):
            return f"{val:.{self._float_digits}f}"
        if isinstance(val, ScaleValue):
            return f"*{val.source}"
        if isinstance(val, PlannerList):
            inner = " ".join(self._repr_value(e) for e in val.elements)
            brackets = {
                BracketKind.ROUND:  ("(", ")"),
                BracketKind.SQUARE: ("[", "]"),
                BracketKind.ANGLE:  ("<", ">"),
            }
            l, r = brackets[val.kind]
            return f"{l}{inner}{r}"
        return repr(val)

    def _repr_form(self, node: FormNode) -> str:
        if isinstance(node, IdentNode):
            return node.name
        if isinstance(node, IntNode):
            return str(node.value)
        if isinstance(node, FloatNode):
            return str(node.value)
        if isinstance(node, ScaleNode):
            return f"*{node.source}"
        if isinstance(node, VarRefNode):
            prefix = {
                (VarMode.READ,   False): ".",
                (VarMode.ASSIGN, False): "*",
                (VarMode.CONST,  False): ":",
                (VarMode.READ,   True):  "!.",
                (VarMode.ASSIGN, True):  "!*",
                (VarMode.CONST,  True):  "!:",
            }[(node.mode, node.segmented)]
            return prefix + node.name
        if isinstance(node, LListNode):
            inner = " ".join(self._repr_form(e) for e in node.elements)
            return f"({inner})"
        if isinstance(node, CallNode):
            lb = "<" if node.segmented else "["
            rb = ">" if node.segmented else "]"
            parts = [self._repr_form(node.head)] + [self._repr_form(a) for a in node.args]
            return f"{lb}{' '.join(parts)}{rb}"
        return repr(node)
