from src.interpreter.functions.matching.core import match_bt
from src.interpreter.functions.matching import type_, numeric, logic, special
from src.interpreter.values import NIL, T
from src.interpreter.errors import PlannerRuntimeError


def _is(raw_args, interp):
    if len(raw_args) != 2:
        raise PlannerRuntimeError("IS: ожидается образец и выражение")
    pat_node, expr_node = raw_args
    expr = (yield from interp.eval_first_bt(expr_node))
    mark = interp._trail.mark()
    if (yield from match_bt(pat_node, expr, interp)):
        yield T
        return
    interp._trail.undo_to(mark)
    yield NIL


def register_all(interp) -> None:
    for mod in (type_, numeric, logic, special):
        mod.register(interp._matchers, interp)

    interp._bt_fsubrs["IS"] = lambda raw_args: _is(raw_args, interp)
