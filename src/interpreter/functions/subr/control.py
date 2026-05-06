from src.interpreter.models.values import Value
from src.interpreter.models.signals import PlannerRuntimeError, _GoSignal, _ReturnSignal


def go(args: list, interp) -> Value:
    interp._check_arity("GO", args, 1)
    label = args[0]
    if not isinstance(label, str):
        raise PlannerRuntimeError("GO: аргумент должен быть идентификатором")
    raise _GoSignal(label)


def return_(args: list, interp) -> Value:
    interp._check_arity("RETURN", args, 1)
    raise _ReturnSignal(args[0])


def register(interp) -> None:
    interp._subrs["GO"]     = lambda args: go(args, interp)
    interp._subrs["RETURN"] = lambda args: return_(args, interp)
