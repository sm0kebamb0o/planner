from src.interpreter.control_flow import EvalStream

from src.interpreter.values import NIL, T, _is_true, Value


def or_(raw_args: list, interp) -> EvalStream:
    for arg in raw_args:
        val = (yield from interp.eval_first_bt(arg))
        if _is_true(val):
            yield val
            return
    yield NIL


def and_(raw_args: list, interp) -> EvalStream:
    last: Value = T
    for arg in raw_args:
        last = (yield from interp.eval_first_bt(arg))
        if not _is_true(last):
            yield NIL
            return
    yield last


def register(interp) -> None:
    interp._bt_fsubrs["OR"]  = lambda raw: or_(raw, interp)
    interp._bt_fsubrs["AND"] = lambda raw: and_(raw, interp)
