from dataclasses import dataclass
from typing import Union

from src.parser.ast.nodes import FormNode


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