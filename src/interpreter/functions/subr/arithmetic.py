import math
import random

from src.interpreter.models.values import NIL, T, PlannerList, BracketKind, Value
from src.interpreter.models.signals import PlannerRuntimeError


def add(args: list) -> Value:
    if not args:
        raise PlannerRuntimeError("+: нужен хотя бы один аргумент")
    total: int | float = 0
    for a in args:
        total = total + _as_number("+", a)
    return total


def sub(args: list, interp) -> Value:
    interp._check_arity("-", args, 2)
    return interp._as_number("-", args[0]) - interp._as_number("-", args[1])


def mul(args: list) -> Value:
    if not args:
        raise PlannerRuntimeError("×: нужен хотя бы один аргумент")
    result: int | float = 1
    for a in args:
        result = result * _as_number("×", a)
    return result


def div(args: list, interp) -> Value:
    interp._check_arity("/", args, 2)
    n2 = interp._as_number("/", args[1])
    if n2 == 0:
        raise PlannerRuntimeError("/: деление на ноль")
    return float(interp._as_number("/", args[0])) / float(n2)


def idiv(args: list, interp) -> Value:
    interp._check_arity("DIV", args, 2)
    n1 = interp._as_number("DIV", args[0])
    n2 = interp._as_number("DIV", args[1])
    if n2 == 0:
        raise PlannerRuntimeError("DIV: деление на ноль")
    return int(math.floor(n1 / n2))


def mod(args: list, interp) -> Value:
    interp._check_arity("MOD", args, 2)
    n1 = interp._as_number("MOD", args[0])
    n2 = interp._as_number("MOD", args[1])
    if n2 == 0:
        raise PlannerRuntimeError("MOD: деление на ноль")
    return n1 - n2 * math.floor(n1 / n2)


def power(args: list, interp) -> Value:
    interp._check_arity("↑", args, 2)
    base = interp._as_number("↑", args[0])
    exp  = interp._as_number("↑", args[1])
    result = base ** exp
    if isinstance(base, int) and isinstance(exp, int) and exp >= 0:
        return int(result)
    return float(result)


def abs_(args: list, interp) -> Value:
    interp._check_arity("ABS", args, 1)
    return abs(interp._as_number("ABS", args[0]))


def entier(args: list, interp) -> Value:
    interp._check_arity("ENTIER", args, 1)
    return int(math.floor(interp._as_number("ENTIER", args[0])))


def round_(args: list, interp) -> Value:
    interp._check_arity("ROUND", args, 1)
    return int(math.floor(interp._as_number("ROUND", args[0]) + 0.5))


def sign(args: list, interp) -> Value:
    interp._check_arity("SIGN", args, 1)
    x = interp._as_number("SIGN", args[0])
    return 1 if x > 0 else (0 if x == 0 else -1)


def sqrt_(args: list, interp) -> Value:
    interp._check_arity("SQRT", args, 1)
    return math.sqrt(float(interp._as_number("SQRT", args[0])))


def max_(args: list, interp) -> Value:
    if not args:
        raise PlannerRuntimeError("MAX: нужен хотя бы один аргумент")
    return max(interp._as_number("MAX", a) for a in args)


def min_(args: list, interp) -> Value:
    if not args:
        raise PlannerRuntimeError("MIN: нужен хотя бы один аргумент")
    return min(interp._as_number("MIN", a) for a in args)


def random_(args: list) -> Value:
    return random.random()


def _as_number(fn: str, val) -> int | float:
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val
    raise PlannerRuntimeError(f"{fn}: ожидалось число, получено {val!r}")


def register(interp) -> None:
    interp._subrs["+"]      = add
    interp._subrs["-"]      = lambda args: sub(args, interp)
    interp._subrs["×"]      = mul
    interp._subrs["*"]      = mul
    interp._subrs["/"]      = lambda args: div(args, interp)
    interp._subrs["DIV"]    = lambda args: idiv(args, interp)
    interp._subrs["MOD"]    = lambda args: mod(args, interp)
    interp._subrs["↑"]      = lambda args: power(args, interp)
    interp._subrs["ABS"]    = lambda args: abs_(args, interp)
    interp._subrs["ENTIER"] = lambda args: entier(args, interp)
    interp._subrs["ROUND"]  = lambda args: round_(args, interp)
    interp._subrs["SIGN"]   = lambda args: sign(args, interp)
    interp._subrs["SQRT"]   = lambda args: sqrt_(args, interp)
    interp._subrs["MAX"]    = lambda args: max_(args, interp)
    interp._subrs["MIN"]    = lambda args: min_(args, interp)
    interp._subrs["RANDOM"] = random_
