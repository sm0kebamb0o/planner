from src.interpreter.values import NIL, _is_true
from src.interpreter.signals import PlannerFailure


def gate(raw_args: list, interp):
    if not raw_args:
        return NIL
    try:
        return next(interp._eval_body_bt(raw_args))
    except StopIteration:
        return NIL
    except PlannerFailure as f:
        if f.target is not None:
            raise
        interp._last_failure = f.message if f.message is not None else NIL
        return NIL


def unfalse(raw_args: list, interp):
    try:
        val = next(interp._eval_body_bt(raw_args))
    except StopIteration:
        raise PlannerFailure()
    except PlannerFailure:
        raise
    if not _is_true(val):
        raise PlannerFailure()
    return val


def register(interp) -> None:
    interp._fsubrs["GATE"]    = lambda raw: gate(raw, interp)
    interp._fsubrs["UNFALSE"] = lambda raw: unfalse(raw, interp)
