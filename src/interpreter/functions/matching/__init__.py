from src.interpreter.functions.matching.core import match
from src.interpreter.functions.matching import type_, numeric, logic, special
from src.interpreter.values import NIL, T
from src.interpreter.errors import PlannerRuntimeError


def register_all(interp) -> None:
    for mod in (type_, numeric, logic, special):
        mod.register(interp._matchers, interp)

    def _is(raw_args):
        if len(raw_args) != 2:
            raise PlannerRuntimeError("IS: ожидается образец и выражение")
        pat_node, expr_node = raw_args
        expr = interp.eval_form(expr_node)
        mark = interp._trail.mark()
        if match(pat_node, expr, interp):
            return T
        interp._trail.undo_to(mark)
        return NIL

    interp._fsubrs["IS"] = _is
