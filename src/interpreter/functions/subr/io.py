from src.interpreter.models.values import PlannerList, BracketKind, Value
from src.interpreter.models.signals import PlannerRuntimeError


def print_(args: list, interp) -> Value:
    interp._check_arity("PRINT", args, 1)
    print(interp._repr_value(args[0]))
    return args[0]


def mprint(args: list, interp) -> Value:
    print(" ".join(interp._repr_value(a) for a in args))
    return PlannerList(elements=list(args), kind=BracketKind.ROUND)


def digits(args: list, interp) -> Value:
    if not args:
        return interp._float_digits
    n = interp._as_int("DIGITS", args[0])
    if n < 0:
        raise PlannerRuntimeError("DIGITS: число цифр не может быть отрицательным")
    interp._float_digits = n
    return n


def eval_(args: list, interp) -> Value:
    interp._check_arity("EVAL", args, 1)
    ast_node = interp._value_to_form(args[0])
    return interp.eval_form(ast_node)


def register(interp) -> None:
    interp._subrs["PRINT"]  = lambda args: print_(args, interp)
    interp._subrs["MPRINT"] = lambda args: mprint(args, interp)
    interp._subrs["DIGITS"] = lambda args: digits(args, interp)
    interp._subrs["EVAL"]   = lambda args: eval_(args, interp)
