from src.interpreter.values import NIL, _is_true
from src.interpreter.signals import PlannerFailure
from src.interpreter.control_flow import ControlExhausted


def gate(raw_args: list, interp):
    if not raw_args:
        yield NIL
        return
    try:
        val = yield from interp._first_value_bt(interp._eval_body_bt(raw_args))
    except PlannerFailure as f:
        if isinstance(f, ControlExhausted) or f.target is not None:
            raise
        interp._last_failure = f.message if f.message is not None else NIL
        val = NIL
    yield val


def unfalse(raw_args: list, interp):
    val = yield from interp._first_value_bt(interp._eval_body_bt(raw_args))
    if not _is_true(val):
        raise PlannerFailure()
    yield val


def register(interp) -> None:
    interp._bt_fsubrs["GATE"]    = lambda raw: gate(raw, interp)
    interp._bt_fsubrs["UNFALSE"] = lambda raw: unfalse(raw, interp)
