from src.interpreter.values import Value, NIL
from src.interpreter.signals import GoSignal, ReturnSignal
from src.interpreter.errors import PlannerRuntimeError


def go(args: list, interp) -> Value:
    interp._check_arity("GO", args, 1)
    label = args[0]
    if not isinstance(label, str):
        raise PlannerRuntimeError("GO: аргумент должен быть идентификатором")
    raise GoSignal(label)


def return_(args: list, interp) -> Value:
    interp._check_arity("RETURN", args, 1)
    raise ReturnSignal(args[0])


def exit_(args: list, interp) -> Value:
    val = args[0] if args else NIL
    raise ReturnSignal(val)


def register(interp) -> None:
    interp._subrs["GO"]     = lambda args: go(args, interp)
    interp._subrs["RETURN"] = lambda args: return_(args, interp)
    interp._subrs["EXIT"]   = lambda args: exit_(args, interp)
