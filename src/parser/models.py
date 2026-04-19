from dataclasses import dataclass, field

from .utils import AutoIdMeta


@dataclass
class Neterminal(metaclass=AutoIdMeta):
    value : str
    id    : str = field(init=False)

    def __eq__(self, other: "Neterminal") -> bool:
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value


@dataclass
class Terminal(metaclass=AutoIdMeta):
    value : str
    id    : str = field(init=False)

    def __eq__(self, other: "Terminal") -> bool:
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value
