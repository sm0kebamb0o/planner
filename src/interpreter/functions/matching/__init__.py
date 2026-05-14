from src.interpreter.functions.matching.core import match
from src.interpreter.functions.matching import type_, numeric, logic, special
from src.interpreter.values import NIL, T
from src.interpreter.errors import PlannerRuntimeError


def _is(raw_args, interp):
    if len(raw_args) != 2:
        raise PlannerRuntimeError("IS: ожидается образец и выражение")
    pat_node, expr_node = raw_args
    expr = interp.eval_form(expr_node)
    mark = interp._trail.mark()
    if match(pat_node, expr, interp):
        return T
    interp._trail.undo_to(mark)
    return NIL


def register_all(interp) -> None:
    for mod in (type_, numeric, logic, special):
        mod.register(interp._matchers, interp)

    interp._fsubrs["IS"] = lambda raw_args: _is(raw_args, interp)
