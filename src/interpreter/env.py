from dataclasses import dataclass, field

from src.interpreter.models.signals import PlannerRuntimeError
from src.interpreter.models.values import Value


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