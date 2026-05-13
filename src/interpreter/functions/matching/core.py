from __future__ import annotations

from src.parser.ast.nodes import (
    FormNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)
from src.interpreter.values import BracketKind, PlannerList, ScaleValue


def _bind(name: str, val, interp) -> None:
    if interp.env.has_value(name):
        old = interp.env.get_local(name)
        interp._trail.push_undo(lambda n=name, o=old: interp.env.set_local(n, o))
    else:
        interp._trail.push_undo(lambda n=name: interp.env.unassign(n))
    interp.env.set_local(name, val)


def _is_segmented(pat: FormNode) -> bool:
    if isinstance(pat, VarRefNode):
        return pat.segmented
    if isinstance(pat, CallNode):
        return pat.segmented
    return False


def match(pat: FormNode, expr, interp) -> bool:
    if isinstance(pat, IdentNode):
        return expr == pat.name

    if isinstance(pat, IntNode):
        return expr == pat.value

    if isinstance(pat, FloatNode):
        return expr == pat.value

    if isinstance(pat, ScaleNode):
        return isinstance(expr, ScaleValue) and expr.bits == pat.bits

    if isinstance(pat, VarRefNode) and not pat.segmented:
        if pat.mode == VarMode.ASSIGN:
            _bind(pat.name, expr, interp)
            return True
        if pat.mode == VarMode.READ:
            if interp.env.has_value(pat.name):
                return interp.env.get_local(pat.name) == expr
            _bind(pat.name, expr, interp)
            return True
        if pat.mode == VarMode.CONST:
            if not interp.env.has_constant(pat.name):
                return False
            return interp.env.get_constant(pat.name) == expr

    if isinstance(pat, LListNode):
        if not isinstance(expr, PlannerList) or expr.kind != BracketKind.ROUND:
            return False
        if not any(_is_segmented(p) for p in pat.elements):
            if len(pat.elements) != len(expr.elements):
                return False
            for p, e in zip(pat.elements, expr.elements):
                if not match(p, e, interp):
                    return False
            return True
        return match_list(pat.elements, expr.elements, 0, 0, interp)

    if isinstance(pat, CallNode) and not pat.args and isinstance(pat.head, IdentNode) and not pat.head.name:
        return True

    if isinstance(pat, CallNode) and isinstance(pat.head, IdentNode):
        matcher_name = pat.head.name
        if matcher_name in interp._matchers:
            return interp._matchers[matcher_name](pat.args, expr, interp)
        val = interp.eval_form(pat)
        return val == expr

    try:
        val = interp.eval_form(pat)
        return val == expr
    except Exception:
        return False


def match_list(
    pats: list[FormNode],
    items: list,
    pi: int,
    ii: int,
    interp,
) -> bool:
    if pi == len(pats) and ii == len(items):
        return True
    if pi == len(pats):
        return False
    if ii == len(items):
        return _all_wildcards(pats, pi, items, ii, interp)

    pat = pats[pi]
    if _is_segmented(pat):
        return _match_segment(pat, pats, items, pi, ii, interp)
    else:
        mark = interp._trail.mark()
        if match(pat, items[ii], interp):
            if match_list(pats, items, pi + 1, ii + 1, interp):
                return True
        interp._trail.undo_to(mark)
        return False


def _try_bind_segment(seg_pat: FormNode, seg_list, interp) -> bool:
    if isinstance(seg_pat, VarRefNode):
        if seg_pat.mode == VarMode.ASSIGN:
            _bind(seg_pat.name, seg_list, interp)
            return True
        if seg_pat.mode == VarMode.READ:
            if interp.env.has_value(seg_pat.name):
                return interp.env.get_local(seg_pat.name) == seg_list
            _bind(seg_pat.name, seg_list, interp)
            return True
        if seg_pat.mode == VarMode.CONST:
            if interp.env.has_constant(seg_pat.name):
                return interp.env.get_constant(seg_pat.name) == seg_list
            return False

    if isinstance(seg_pat, CallNode) and seg_pat.segmented:
        if not seg_pat.args:
            return True
        if isinstance(seg_pat.head, IdentNode):
            name = seg_pat.head.name
            if name in interp._matchers:
                return interp._matchers[name](seg_pat.args, seg_list, interp)
        return False

    return False


def _match_segment(
    seg_pat: FormNode,
    pats: list[FormNode],
    items: list,
    pi: int,
    ii: int,
    interp,
) -> bool:
    max_remaining = len(items) - ii
    min_needed = sum(1 for p in pats[pi + 1:] if not _is_segmented(p))
    max_seg_len = max_remaining - min_needed

    for seg_len in range(0, max_seg_len + 1):
        mark = interp._trail.mark()
        segment = items[ii: ii + seg_len]
        seg_list = PlannerList(elements=list(segment), kind=BracketKind.ROUND)

        if _try_bind_segment(seg_pat, seg_list, interp):
            if match_list(pats, items, pi + 1, ii + seg_len, interp):
                return True

        interp._trail.undo_to(mark)

    return False


def _all_wildcards(
    pats: list[FormNode],
    pi: int,
    items: list,
    ii: int,
    interp,
) -> bool:
    empty = PlannerList(elements=[], kind=BracketKind.ROUND)
    for p in pats[pi:]:
        if not _is_segmented(p):
            return False
        if isinstance(p, VarRefNode):
            if p.mode == VarMode.ASSIGN:
                _bind(p.name, empty, interp)
            elif p.mode == VarMode.READ:
                if interp.env.has_value(p.name):
                    if interp.env.get_local(p.name) != empty:
                        return False
                else:
                    _bind(p.name, empty, interp)
            elif p.mode == VarMode.CONST:
                if not interp.env.has_constant(p.name):
                    return False
                if interp.env.get_constant(p.name) != empty:
                    return False
        elif isinstance(p, CallNode) and p.segmented:
            if not p.args:
                pass
            else:
                if isinstance(p.head, IdentNode) and p.head.name in interp._matchers:
                    if not interp._matchers[p.head.name](p.args, empty, interp):
                        return False
                else:
                    return False
        else:
            return False
    return True
