import math
from collections.abc import Sequence

from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions.codec import repr_value
from src.interpreter.values import PlannerList, ScaleValue, Value


def check_arity(
    name: str,
    args: Sequence[object],
    expected: int,
    maximum: int | None = None,
) -> None:
    """Проверяет точное число аргументов или попадание в диапазон с включёнными границами."""
    upper = expected if maximum is None else maximum
    if not expected <= len(args) <= upper:
        count = str(expected) if upper == expected else f"{expected}-{upper}"
        raise PlannerRuntimeError(
            f"{name}: ожидалось {count} аргументов, получено {len(args)}"
        )


def as_number(name: str, value: Value, *, float_digits: int = 6) -> int | float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    raise PlannerRuntimeError(
        f"{name}: ожидалось число, получено {repr_value(value, float_digits)!r}"
    )


def as_int(name: str, value: Value, *, float_digits: int = 6) -> int:
    number = as_number(name, value, float_digits=float_digits)
    return int(math.floor(float(number) + 0.5))


def as_list(name: str, value: Value, *, float_digits: int = 6) -> PlannerList:
    if isinstance(value, PlannerList):
        return value
    raise PlannerRuntimeError(
        f"{name}: ожидался список, получено {repr_value(value, float_digits)!r}"
    )


def as_scale(name: str, value: Value, *, float_digits: int = 6) -> ScaleValue:
    if isinstance(value, ScaleValue):
        return value
    raise PlannerRuntimeError(
        f"{name}: ожидалась шкала, получено {repr_value(value, float_digits)!r}"
    )


def as_ident(value: Value, *, float_digits: int = 6) -> str:
    if isinstance(value, str):
        return value
    raise PlannerRuntimeError(
        f"Ожидался идентификатор, получено {repr_value(value, float_digits)!r}"
    )
