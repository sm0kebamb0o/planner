from src.interpreter.models.values import NIL, _is_true
from src.interpreter.models.signals import PlannerFailure
from src.parser.ast_nodes import LListNode


def gate_all(raw_args: list, interp):
    """GATE в режиме всех решений: перебирает первый аргумент в BT-режиме."""
    if not raw_args:
        return NIL
    last = NIL
    for val in interp.eval_form_bt(raw_args[0]):
        try:
            last = val
            for node in raw_args[1:]:
                last = interp.eval_form(node)
            return last
        except PlannerFailure as f:
            if f.target is not None:
                raise
            interp._last_failure = f.message if f.message is not None else NIL
            continue
    return NIL


def unfalse(raw_args: list, interp):
    """UNFALSE e1 e2 ... — если вычисление неуспешно или значение () → FAIL."""
    mark = interp._trail.mark()
    try:
        val = NIL
        for node in raw_args:
            val = interp.eval_form(node)
        if not _is_true(val):
            interp._trail.undo_to(mark)
            raise PlannerFailure(message="UNFALSE")
        return val
    except PlannerFailure:
        interp._trail.undo_to(mark)
        raise


def register(interp) -> None:
    interp._fsubrs["GATE"]    = lambda raw: gate_all(raw, interp)
    interp._fsubrs["UNFALSE"] = lambda raw: unfalse(raw, interp)
