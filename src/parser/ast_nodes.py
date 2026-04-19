from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Union


class VarMode(Enum):
    READ   = auto()   # .X  / !.X  — read local variable
    ASSIGN = auto()   # *X  / !*X  — assign local variable (L-value)
    CONST  = auto()   # :X  / !:X  — read global constant


@dataclass
class ProgramNode:
    forms: list[FormNode]

    def __repr__(self) -> str:
        return f"ProgramNode({len(self.forms)} forms)"


@dataclass
class IdentNode:
    name: str

    def __repr__(self) -> str:
        return f"Ident({self.name!r})"


@dataclass
class IntNode:
    value: int

    def __repr__(self) -> str:
        return f"Int({self.value})"


@dataclass
class FloatNode:
    value: float

    def __repr__(self) -> str:
        return f"Float({self.value})"


@dataclass
class ScaleNode:
    bits: int
    source: str = field(repr=False)  # original octal text, e.g. "3704"

    def __repr__(self) -> str:
        return f"Scale(*{self.source})"


@dataclass
class VarRefNode:
    mode     : VarMode
    name     : str
    segmented: bool = False

    def __repr__(self) -> str:
        prefix = {
            (VarMode.READ,   False): ".",
            (VarMode.ASSIGN, False): "*",
            (VarMode.CONST,  False): ":",
            (VarMode.READ,   True):  "!.",
            (VarMode.ASSIGN, True):  "!*",
            (VarMode.CONST,  True):  "!:",
        }[(self.mode, self.segmented)]
        return f"VarRef({prefix}{self.name})"


@dataclass
class LListNode:
    elements: list[FormNode]

    def __repr__(self) -> str:
        return f"LList({self.elements!r})"


@dataclass
class CallNode:
    head     : FormNode
    args     : list[FormNode]
    segmented: bool = False

    def __repr__(self) -> str:
        lb = "<" if self.segmented else "["
        rb = ">" if self.segmented else "]"
        inner = " ".join(repr(a) for a in [self.head] + self.args)
        return f"Call{lb}{inner}{rb}"


FormNode = Union[
    IdentNode,
    IntNode,
    FloatNode,
    ScaleNode,
    VarRefNode,
    LListNode,
    CallNode,
]
