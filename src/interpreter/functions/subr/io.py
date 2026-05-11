from src.interpreter.values import PlannerList, BracketKind, Value
from src.interpreter.signals import PlannerRuntimeError
from src.interpreter.functions import codec


def print_(args: list, interp) -> Value:
    interp._check_arity("PRINT", args, 1)
    print(codec.repr_value(args[0], interp._float_digits))
    return args[0]


def mprint(args: list, interp) -> Value:
    print(" ".join(codec.repr_value(a, interp._float_digits) for a in args))
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
    ast_node = codec.value_to_form(args[0])
    return interp.eval_form(ast_node)


def register(interp) -> None:
    interp._subrs["PRINT"]  = lambda args: print_(args, interp)
    interp._subrs["MPRINT"] = lambda args: mprint(args, interp)
    interp._subrs["DIGITS"] = lambda args: digits(args, interp)
    interp._subrs["EVAL"]   = lambda args: eval_(args, interp)
