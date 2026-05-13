from src.interpreter.functions.backtracking.utils import _tracked_gen
from src.interpreter.signals import PlannerFailure
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.values import NIL


def alt(raw_args: list, interp):
    def _gen():
        for expr in raw_args:
            mark = interp._trail.mark()
            try:
                val = interp.eval_form(expr)
                yield val
                interp._trail.undo_to(mark)
            except PlannerFailure as f:
                interp._trail.undo_to(mark)
                if f.target is not None:
                    raise
                interp._last_failure = f.message if f.message is not None else NIL

    yield from _tracked_gen(_gen(), interp)


def fp(raw_args: list, interp):
    if not raw_args:
        raise PlannerRuntimeError("FP: нужно имя развилки и хотя бы одна альтернатива")

    name = str(interp.eval_form(raw_args[0]))
    alt_args = raw_args[1:]

    def _gen():
        for expr in alt_args:
            mark = interp._trail.mark()
            try:
                val = interp.eval_form(expr)
                yield val
                interp._trail.undo_to(mark)
            except PlannerFailure as f:
                interp._trail.undo_to(mark)
                if f.target == name:
                    interp._last_failure = f.message if f.message is not None else NIL
                elif f.target is not None:
                    raise
                else:
                    interp._last_failure = f.message if f.message is not None else NIL

    yield from _tracked_gen(_gen(), interp)


def register(interp) -> None:
    interp._bt_fsubrs["ALT"] = lambda raw: alt(raw, interp)
    interp._bt_fsubrs["FP"]  = lambda raw: fp(raw, interp)
