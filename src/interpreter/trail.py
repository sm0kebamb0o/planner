from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Trail:

    _ops: list[Callable[[], None]] = field(default_factory=list)

    def mark(self) -> int:
        """Вернуть текущую позицию"""
        return len(self._ops)

    def push_undo(self, fn: Callable[[], None]) -> None:
        """Записать обратный оператор в стек."""
        self._ops.append(fn)

    def undo_to(self, mark: int) -> None:
        """Выполнить операторы с конца до позиции mark."""
        while len(self._ops) > mark:
            self._ops.pop()()

    def discard_to(self, mark: int) -> None:
        """УДалить операторы с позиции mark"""
        del self._ops[mark:]
