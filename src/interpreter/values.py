from enum import Enum, auto
from dataclasses import dataclass
from typing import Union


class BracketKind(Enum):
    ROUND  = auto()
    SQUARE = auto()
    ANGLE  = auto()


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


def _is_true(val: "Value") -> bool:
    return not (isinstance(val, PlannerList) and len(val.elements) == 0)