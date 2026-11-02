from src.interpreter.control_flow import ControlRequest
from src.interpreter.signals import PlannerFailure
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.values import NIL


def alt(raw_args: list, interp):
    for expr in raw_args:
        mark = interp._trail.mark()
        try:
            gen = interp.eval_form_bt(expr)
            try:
                for item in gen:
                    yield item
                    if not isinstance(item, ControlRequest):
                        interp._trail.undo_to(mark)
            finally:
                gen.close()
        except PlannerFailure as f:
            interp._trail.undo_to(mark)
            if f.target is not None:
                raise
            interp._last_failure = f.message if f.message is not None else NIL


def fp(raw_args: list, interp):
    if not raw_args:
        raise PlannerRuntimeError("FP: нужно имя развилки и хотя бы одна альтернатива")

    name = str((yield from interp.eval_first_bt(raw_args[0])))
    alt_args = raw_args[1:]

    for expr in alt_args:
        mark = interp._trail.mark()
        try:
            gen = interp.eval_form_bt(expr)
            try:
                for item in gen:
                    yield item
                    if not isinstance(item, ControlRequest):
                        interp._trail.undo_to(mark)
            finally:
                gen.close()
        except PlannerFailure as f:
            interp._trail.undo_to(mark)
            if f.target == name:
                interp._last_failure = f.message if f.message is not None else NIL
            elif f.target is not None:
                raise
            else:
                interp._last_failure = f.message if f.message is not None else NIL


def register(interp) -> None:
    interp._bt_fsubrs["ALT"] = lambda raw: alt(raw, interp)
    interp._bt_fsubrs["FP"]  = lambda raw: fp(raw, interp)
