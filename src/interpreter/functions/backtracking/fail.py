from src.interpreter.values import NIL
from src.interpreter.signals import PlannerFailure, PlannerRuntimeError


def fail(args: list, interp):
    msg    = args[0] if len(args) >= 1 else NIL
    target = str(args[1]) if len(args) >= 2 else None
    interp._last_failure = msg
    raise PlannerFailure(message=msg, target=target)


def mess(args: list, interp):
    return interp._last_failure


def failex(args: list, interp):
    """FAILEX e fn? — неуспех с передачей управления именованному фрейму fn."""
    if not args:
        raise PlannerRuntimeError("FAILEX: нужен хотя бы один аргумент")
    msg    = args[0]
    target = str(args[1]) if len(args) >= 2 else None
    interp._last_failure = msg
    raise PlannerFailure(message=msg, target=target)


def register(interp) -> None:
    interp._subrs["FAIL"]   = lambda args: fail(args, interp)
    interp._subrs["MESS"]   = lambda args: mess(args, interp)
    interp._subrs["FAILEX"] = lambda args: failex(args, interp)
