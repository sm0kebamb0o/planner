from __future__ import annotations

from src.parser.ast.nodes import IdentNode
from src.interpreter.values import NIL, PlannerList, _is_true
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions import codec
from src.interpreter.functions.matching.core import match, match_list, _is_segmented


def _be(args, expr, interp):
    if not args:
        raise PlannerRuntimeError("BE: нужен аргумент")
    val = interp.eval_form(args[0])
    return val != NIL and _is_true(val)


def _pat(args, expr, interp):
    if not args:
        raise PlannerRuntimeError("PAT: нужен аргумент")
    pat_val = interp.eval_form(args[0])
    pat_node = codec.value_to_form(pat_val)
    return match(pat_node, expr, interp)


def _one_of(args, expr, interp):
    if not args:
        raise PlannerRuntimeError("ONE-OF: нужен список")
    lst = interp.eval_form(args[0])
    if not isinstance(lst, PlannerList):
        raise PlannerRuntimeError("ONE-OF: аргумент должен быть списком")
    return expr in lst.elements


def _linear(args, expr, interp):
    if not isinstance(expr, PlannerList):
        return False
    if not any(_is_segmented(p) for p in args):
        if len(args) != len(expr.elements):
            return False
        for p, e in zip(args, expr.elements):
            if not match(p, e, interp):
                return False
        return True
    return match_list(args, expr.elements, 0, 0, interp)


def _star(args, expr, interp):
    if not isinstance(expr, PlannerList) or not args:
        return False
    pat = args[0]
    for elem in expr.elements:
        mark = interp._trail.mark()
        if not match(pat, elem, interp):
            interp._trail.undo_to(mark)
            return False
    return True


def register(matchers: dict, interp) -> None:
    matchers["BE"]     = lambda args, expr: _be(args, expr, interp)
    matchers["PAT"]    = lambda args, expr: _pat(args, expr, interp)
    matchers["ONE-OF"] = lambda args, expr: _one_of(args, expr, interp)
    matchers["LINEAR"] = lambda args, expr: _linear(args, expr, interp)
    matchers["STAR"]   = lambda args, expr: _star(args, expr, interp)
