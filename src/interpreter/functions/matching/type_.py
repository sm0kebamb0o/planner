from __future__ import annotations

from src.interpreter.values import BracketKind, PlannerList, ScaleValue
from src.interpreter.functions.matching.core import match


def register(matchers: dict, interp) -> None:
    def _type(name: str, predicate):
        matchers[name] = lambda args, expr, interp: predicate(expr)

    _type("ID",     lambda e: isinstance(e, str))
    _type("NUM",    lambda e: isinstance(e, (int, float)) and not isinstance(e, bool))
    _type("INT",    lambda e: isinstance(e, int) and not isinstance(e, bool))
    _type("REAL",   lambda e: isinstance(e, float))
    _type("SCALE",  lambda e: isinstance(e, ScaleValue))
    _type("ATOM",   lambda e: not isinstance(e, PlannerList))
    _type("ATOMIC", lambda e: not isinstance(e, PlannerList))

    def _list_any(kind):
        def fn(args, expr, interp):
            if not isinstance(expr, PlannerList) or expr.kind != kind:
                return False
            if args:
                return match(args[0], len(expr.elements), interp)
            return True
        return fn

    matchers["LIST"]  = _list_any(BracketKind.ROUND)
    matchers["LISTP"] = _list_any(BracketKind.SQUARE)
    matchers["LISTS"] = _list_any(BracketKind.ANGLE)

    def _listr(args, expr, interp):
        if not isinstance(expr, PlannerList):
            return False
        if args:
            return match(args[0], len(expr.elements), interp)
        return True

    matchers["LISTR"] = _listr

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
    _type("VAR",   lambda e: _vdot(e) or _vstar(e) or _vcol(e) or
                              _vsdot(e) or _vsstr(e) or _vscol(e))
