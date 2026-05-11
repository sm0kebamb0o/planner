from src.interpreter.functions.backtracking.utils import _close_forks_since
from src.interpreter.models.signals import PlannerFailure, PlannerRuntimeError
from src.interpreter.models.values import NIL, T, PlannerList, BracketKind, Value
from src.parser.ast.nodes import IdentNode, LListNode

_ALL = object()


def _parse_mode(mode_val):
    if isinstance(mode_val, str) and mode_val == "ALL":
        return _ALL, 0, _ALL
    if isinstance(mode_val, (int, float)):
        q = int(mode_val)
        return q, q, q
    if isinstance(mode_val, PlannerList) and len(mode_val.elements) == 3:
        def _parse_one(v):
            if isinstance(v, str) and v == "ALL":
                return _ALL
            if isinstance(v, (int, float)):
                return int(v)
            raise PlannerRuntimeError(f"FIND: неверный режим {v!r}")
        q, mn, mx = [_parse_one(e) for e in mode_val.elements]
        return q, mn, mx
    raise PlannerRuntimeError(f"FIND: неверный аргумент mode {mode_val!r}")


def find(raw_args: list, interp) -> Value:
    """FIND mode (v1 ... vm) p e1 e2 ... ek"""
    if len(raw_args) < 3:
        raise PlannerRuntimeError("FIND: нужны mode, vars, p и тело")

    mode_node  = raw_args[0]
    vars_node  = raw_args[1]
    p_node     = raw_args[2]
    body_nodes = raw_args[3:]

    mode_val = interp.eval_form(mode_node)
    q, min_, max_ = _parse_mode(mode_val)

    if q == 0:
        return NIL

    if not isinstance(vars_node, LListNode):
        raise PlannerRuntimeError("FIND: второй аргумент — список переменных")

    declared_names = []
    init_bindings  = {}
    for decl in vars_node.elements:
        if isinstance(decl, IdentNode):
            declared_names.append(decl.name)
        elif isinstance(decl, LListNode) and len(decl.elements) == 2:
            name_node = decl.elements[0]
            if not isinstance(name_node, IdentNode):
                raise PlannerRuntimeError("FIND: неверное объявление переменной")
            declared_names.append(name_node.name)
            init_bindings[name_node.name] = interp.eval_form(decl.elements[1])

    depth = len(interp._fork_stack)
    interp.env.push_frame(declared=declared_names, bindings=init_bindings)
    try:
        col_elements = []
        n = 0
        for _ in interp._eval_body_bt(body_nodes):
            p_val = interp.eval_form(p_node)
            n += 1
            col_elements.insert(0, p_val)
            if q is not _ALL and n >= q:
                break

        _close_forks_since(interp, depth)

        ok_min = (min_ is _ALL or n >= min_)
        ok_max = (max_ is _ALL or n <= max_)
        col = PlannerList(elements=col_elements, kind=BracketKind.ROUND)

        if ok_min and ok_max:
            return col

        interp._last_failure = col
        raise PlannerFailure(message=col)
    finally:
        interp.env.pop_frame()


def register(interp) -> None:
    interp._fsubrs["FIND"] = lambda raw: find(raw, interp)
