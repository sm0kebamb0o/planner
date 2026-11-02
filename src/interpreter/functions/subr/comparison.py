from src.interpreter.values import NIL, T, Value
from src.interpreter.functions.utils import as_number


def _bool(cond: bool) -> Value:
    return T if cond else NIL


def eq(args: list) -> Value:
    return _bool(len(args) == 2 and args[0] == args[1])


def neq(args: list) -> Value:
    return _bool(len(args) == 2 and args[0] != args[1])


def gt(args: list, interp) -> Value:
    return _bool(
        len(args) == 2
        and as_number("GT", args[0], float_digits=interp._float_digits)
        > as_number("GT", args[1], float_digits=interp._float_digits)
    )


def ge(args: list, interp) -> Value:
    return _bool(
        len(args) == 2
        and as_number("GE", args[0], float_digits=interp._float_digits)
        >= as_number("GE", args[1], float_digits=interp._float_digits)
    )


def lt(args: list, interp) -> Value:
    return _bool(
        len(args) == 2
        and as_number("LT", args[0], float_digits=interp._float_digits)
        < as_number("LT", args[1], float_digits=interp._float_digits)
    )


def le(args: list, interp) -> Value:
    return _bool(
        len(args) == 2
        and as_number("LE", args[0], float_digits=interp._float_digits)
        <= as_number("LE", args[1], float_digits=interp._float_digits)
    )


def register(interp) -> None:
    interp._subrs["EQ"]  = eq
    interp._subrs["NEQ"] = neq
    interp._subrs["GT"]  = lambda args: gt(args, interp)
    interp._subrs["GE"]  = lambda args: ge(args, interp)
    interp._subrs["LT"]  = lambda args: lt(args, interp)
    interp._subrs["LE"]  = lambda args: le(args, interp)
