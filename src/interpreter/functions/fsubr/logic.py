from src.interpreter.values import NIL, T, _is_true, Value


def or_(raw_args: list, interp) -> Value:
    for arg in raw_args:
        val = interp.eval_form(arg)
        if _is_true(val):
            return val
    return NIL


def and_(raw_args: list, interp) -> Value:
    last: Value = T
    for arg in raw_args:
        last = interp.eval_form(arg)
        if not _is_true(last):
            return NIL
    return last


def register(interp) -> None:
    interp._fsubrs["OR"]  = lambda raw: or_(raw, interp)
    interp._fsubrs["AND"] = lambda raw: and_(raw, interp)
