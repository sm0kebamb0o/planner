from src.interpreter.models.values import NIL
from src.interpreter.models.signals import PlannerFailure, PlannerRuntimeError
from .utils import _tracked_gen


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
    """FP name e1 e2 ... — именованная развилка.

    При (FAIL msg NAME) адресованный неуспех перебрасывается без метки.
    """
    if not raw_args:
        raise PlannerRuntimeError("FP: нужно имя развилки и хотя бы одна альтернатива")

    name     = str(interp.eval_form(raw_args[0]))
    alt_args = raw_args[1:]

    def _gen():
        try:
            yield from alt(alt_args, interp)
        except PlannerFailure as f:
            if f.target == name:
                raise PlannerFailure(message=f.message)
            raise

    yield from _tracked_gen(_gen(), interp)


def register(interp) -> None:
    interp._bt_fsubrs["ALT"] = lambda raw: alt(raw, interp)
    interp._bt_fsubrs["FP"]  = lambda raw: fp(raw, interp)
