from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass

from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.values import BracketKind, NIL, PlannerList, Value


@dataclass
class Assertion:
    id: int
    value: PlannerList
    properties: dict[str, Value]


def property_map(value: Value) -> dict[str, Value]:
    if not isinstance(value, PlannerList) or value.kind != BracketKind.ROUND:
        raise PlannerRuntimeError("База данных: свойства должны быть L-списком")
    if len(value.elements) % 2:
        raise PlannerRuntimeError("База данных: свойства задаются парами имя/значение")
    result: dict[str, Value] = {}
    for name, item in zip(value.elements[::2], value.elements[1::2]):
        if not isinstance(name, str):
            raise PlannerRuntimeError("База данных: имя свойства должно быть идентификатором")
        if item == NIL:
            result.pop(name, None)
        else:
            result[name] = deepcopy(item)
    return result


def property_list(properties: dict[str, Value]) -> PlannerList:
    return PlannerList([deepcopy(item) for pair in properties.items() for item in pair])


class Database:
    def __init__(self) -> None:
        self._entries: dict[int, Assertion] = {}
        self._next_id = 0

    def ids(self) -> Iterator[int]:
        return iter(sorted(self._entries))

    def get(self, record_id: int) -> Assertion | None:
        entry = self._entries.get(record_id)
        return deepcopy(entry) if entry is not None else None

    def find(self, value: PlannerList) -> Assertion | None:
        for record_id in self.ids():
            entry = self._entries[record_id]
            if entry.value == value:
                return deepcopy(entry)
        return None

    def insert(self, value: PlannerList, properties: dict[str, Value]) -> Assertion | None:
        if not isinstance(value, PlannerList) or value.kind != BracketKind.ROUND:
            raise PlannerRuntimeError("База данных: утверждение должно быть L-списком")
        if self.find(value) is not None:
            return None
        entry = Assertion(self._next_id, deepcopy(value), deepcopy(properties))
        self._next_id += 1
        self._entries[entry.id] = entry
        return deepcopy(entry)

    def remove(self, record_id: int) -> Assertion | None:
        return self._entries.pop(record_id, None)

    def restore(self, entry: Assertion) -> None:
        # Откат старой записи не должен заменять более новое постоянное утверждение.
        if self.find(entry.value) is None:
            self._entries[entry.id] = deepcopy(entry)

    def set_property(self, record_id: int, name: str, value: Value) -> None:
        entry = self._entries.get(record_id)
        if entry is None:
            return
        if value == NIL:
            entry.properties.pop(name, None)
        else:
            entry.properties[name] = deepcopy(value)
