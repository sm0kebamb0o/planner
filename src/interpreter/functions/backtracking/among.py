from src.interpreter.models.values import PlannerList
from src.interpreter.models.signals import PlannerRuntimeError
from .utils import _tracked_gen


def among(raw_args: list, interp):
    if not raw_args:
        raise PlannerRuntimeError("AMONG: нужен аргумент")

    lst = interp.eval_form(raw_args[0])
    if not isinstance(lst, PlannerList) or not lst.elements:
        interp._last_failure = "AMONG"
        return

    def _gen():
        for elem in lst.elements:
            mark = interp._trail.mark()
            yield elem
            interp._trail.undo_to(mark)

    yield from _tracked_gen(_gen(), interp)


def register(interp) -> None:
    interp._bt_fsubrs["AMONG"] = lambda raw: among(raw, interp)
