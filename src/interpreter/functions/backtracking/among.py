from src.interpreter.control_flow import ControlRequest
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.values import PlannerList


def among(raw_args: list, interp):
    if not raw_args:
        raise PlannerRuntimeError("AMONG: нужен аргумент")

    gen = interp.eval_form_bt(raw_args[0])
    try:
        for lst in gen:
            if isinstance(lst, ControlRequest):
                yield lst
                continue
            if not isinstance(lst, PlannerList) or not lst.elements:
                interp._last_failure = "AMONG"
                continue

            for elem in lst.elements:
                mark = interp._trail.mark()
                yield elem
                interp._trail.undo_to(mark)

    finally:
        gen.close()


def register(interp) -> None:
    interp._bt_fsubrs["AMONG"] = lambda raw: among(raw, interp)
