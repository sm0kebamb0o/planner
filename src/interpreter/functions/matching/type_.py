from __future__ import annotations

from src.interpreter.values import BracketKind, PlannerList, ScaleValue
from src.interpreter.functions.matching.core import match_bt


def register(matchers: dict, interp) -> None:
    def _type(name: str, predicate, match_length: bool = False):
        def matcher(args, expr):
            if not predicate(expr):
                return False
            if match_length and args:
                return (yield from match_bt(args[0], len(expr.elements), interp))
            return True

        matchers[name] = matcher

    _type("ID",     lambda e: isinstance(e, str))
    _type("NUM",    lambda e: isinstance(e, (int, float)))
    _type("INT",    lambda e: isinstance(e, int))
    _type("REAL",   lambda e: isinstance(e, float))
    _type("SCALE",  lambda e: isinstance(e, ScaleValue))
    _type("ATOM",   lambda e: not isinstance(e, PlannerList))
    _type("ATOMIC", lambda e: not isinstance(e, PlannerList))

    _type("LIST",  lambda e: isinstance(e, PlannerList) and e.kind == BracketKind.ROUND, True)
    _type("LISTP", lambda e: isinstance(e, PlannerList) and e.kind == BracketKind.SQUARE, True)
    _type("LISTS", lambda e: isinstance(e, PlannerList) and e.kind == BracketKind.ANGLE, True)
    _type("LISTR", lambda e: isinstance(e, PlannerList), True)

    def _var_ref_check(prefix: str):
        def check(expr) -> bool:
            return (
                isinstance(expr, PlannerList) and
                expr.kind == BracketKind.ROUND and
                len(expr.elements) == 1 and
                isinstance(expr.elements[0], str) and
                expr.elements[0].startswith(prefix) and
                len(expr.elements[0]) > len(prefix)
            )
        return check

    _vdot  = _var_ref_check(".")
    _vstar = _var_ref_check("*")
    _vcol  = _var_ref_check(":")
    _vsdot = _var_ref_check("!.")
    _vsstr = _var_ref_check("!*")
    _vscol = _var_ref_check("!:")

    _type("VAR.",  _vdot)
    _type("VAR*",  _vstar)
    _type("VAR:",  _vcol)
    _type("VAR!.", _vsdot)
    _type("VAR!*", _vsstr)
    _type("VAR!:", _vscol)
    _type("VARP",  lambda e: _vdot(e) or _vstar(e) or _vcol(e))
    _type("VARS",  lambda e: _vsdot(e) or _vsstr(e) or _vscol(e))
    _type("VAR",   lambda e: _vdot(e) or _vstar(e) or _vcol(e) or _vsdot(e) or _vsstr(e) or _vscol(e))
