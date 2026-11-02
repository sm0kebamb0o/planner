from src.interpreter.control_flow import ControlRequest, EvalStream, ControlExhausted
from src.interpreter.signals import PlannerFailure
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.values import NIL, PlannerList, BracketKind
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


def find(raw_args: list, interp) -> EvalStream:
    if len(raw_args) < 3:
        raise PlannerRuntimeError("FIND: нужны mode, vars, p и тело")

    mode_node  = raw_args[0]
    vars_node  = raw_args[1]
    p_node     = raw_args[2]
    body_nodes = raw_args[3:]

    mode_val = (yield from interp.eval_first_bt(mode_node))
    q, min_, max_ = _parse_mode(mode_val)

    if q == 0:
        yield NIL
        return

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
            init_bindings[name_node.name] = (yield from interp.eval_first_bt(decl.elements[1]))

    interp.env.push_frame(declared=declared_names, bindings=init_bindings)
    gen = interp._eval_body_bt(body_nodes)
    try:
        col_elements = []
        n = 0
        transferred = False
        for item in gen:
            if isinstance(item, ControlRequest):
                transferred = True
                yield item
                continue
            p_val = (yield from interp.eval_first_bt(p_node))
            n += 1
            col_elements.insert(0, p_val)
            if q is not _ALL and n >= q:
                break

        gen.close()

        if transferred and n == 0:
            raise ControlExhausted()

        ok_min = (min_ is _ALL or n >= min_)
        ok_max = (max_ is _ALL or n <= max_)
        col = PlannerList(elements=col_elements, kind=BracketKind.ROUND)

        if not (ok_min and ok_max):
            interp._last_failure = col
            raise PlannerFailure(message=col)
    finally:
        gen.close()
        interp.env.pop_frame()
    yield col


def register(interp) -> None:
    interp._bt_fsubrs["FIND"] = lambda raw: find(raw, interp)
