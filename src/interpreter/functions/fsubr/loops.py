from src.interpreter.values import NIL, _is_true, Value
from src.interpreter.control_flow import ControlRequest, EvalStream
from src.interpreter.errors import PlannerRuntimeError
from src.parser.ast.nodes import IdentNode


def do_(raw_args: list, interp):
    yield from interp._eval_prog_bt([], {}, {}, raw_args)


def loop(raw_args: list, interp) -> EvalStream:
    if len(raw_args) < 2:
        raise PlannerRuntimeError("LOOP: нужны x, l и тело")
    param_node = raw_args[0]
    if not isinstance(param_node, IdentNode):
        raise PlannerRuntimeError("LOOP: первый аргумент должен быть именем переменной")
    param_name = param_node.name
    body_nodes = raw_args[2:]
    lst = (yield from interp.eval_first_bt(raw_args[1]))
    if not hasattr(lst, 'elements'):
        raise PlannerRuntimeError("LOOP: второй аргумент должен быть списком")
    if not lst.elements:
        yield NIL
        return
    interp.env.push_frame([param_name], {})
    try:
        last_val: Value = NIL
        for elem in lst.elements:
            interp.env.set_local(param_name, elem)
            for body_expr in body_nodes:
                last_val = (yield from interp.eval_first_bt(body_expr))
    finally:
        interp.env.pop_frame()
    yield last_val


def _for_bt_chain(body_nodes, param_name, i, n, interp):
    interp.env.set_local(param_name, i)
    gen = interp._eval_body_bt(body_nodes)
    try:
        for body_val in gen:
            if isinstance(body_val, ControlRequest):
                yield body_val
                continue
            if i == n:
                yield body_val
            else:
                yield from _for_bt_chain(body_nodes, param_name, i + 1, n, interp)
            interp.env.set_local(param_name, i)
    finally:
        gen.close()


def for_(raw_args: list, interp):
    if len(raw_args) < 2:
        raise PlannerRuntimeError("FOR: нужны x, n и тело")
    param_node = raw_args[0]
    if not isinstance(param_node, IdentNode):
        raise PlannerRuntimeError("FOR: первый аргумент должен быть именем переменной")
    param_name = param_node.name
    body_nodes = raw_args[2:]
    n_val = (yield from interp.eval_first_bt(raw_args[1]))
    if not isinstance(n_val, (int, float)):
        raise PlannerRuntimeError("FOR: второй аргумент должен быть числом")
    n = int(round(n_val))
    if n < 1:
        yield NIL
        return
    interp.env.push_frame([param_name], {})
    try:
        yield from _for_bt_chain(body_nodes, param_name, 1, n, interp)
    finally:
        interp.env.pop_frame()


def while_(raw_args: list, interp) -> EvalStream:
    if not raw_args:
        raise PlannerRuntimeError("WHILE: нужны условие и тело")
    pred_node  = raw_args[0]
    body_nodes = raw_args[1:]
    while _is_true((yield from interp.eval_first_bt(pred_node))):
        for body_expr in body_nodes:
            (yield from interp.eval_first_bt(body_expr))
    yield NIL


def until(raw_args: list, interp) -> EvalStream:
    if not raw_args:
        raise PlannerRuntimeError("UNTIL: нужны тело и условие")
    body_nodes = raw_args[:-1]
    pred_node  = raw_args[-1]
    while True:
        for body_expr in body_nodes:
            (yield from interp.eval_first_bt(body_expr))
        if _is_true((yield from interp.eval_first_bt(pred_node))):
            break
    yield NIL


def register(interp) -> None:
    interp._bt_fsubrs["DO"] = lambda raw: do_(raw, interp)
    interp._bt_fsubrs["LOOP"]  = lambda raw: loop(raw, interp)
    interp._bt_fsubrs["FOR"]   = lambda raw: for_(raw, interp)
    interp._bt_fsubrs["WHILE"] = lambda raw: while_(raw, interp)
    interp._bt_fsubrs["UNTIL"] = lambda raw: until(raw, interp)
