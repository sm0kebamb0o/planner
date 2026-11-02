from dataclasses import dataclass
from typing import Union

from src.interpreter.errors import PlannerRuntimeError
from src.parser.ast.nodes import FormNode, IdentNode, LListNode, VarMode, VarRefNode


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


def parse_param_spec(var_node: FormNode) -> ParamSpec:
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


@dataclass
class PlannerFunction:
    """Определение пользовательской функции."""
    name:   str
    params: ParamSpec
    body:   FormNode
