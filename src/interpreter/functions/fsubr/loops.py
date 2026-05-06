from src.interpreter.models.values import NIL, _is_true, Value
from src.interpreter.models.signals import PlannerRuntimeError
from src.parser.ast_nodes import IdentNode


def do_(raw_args: list, interp) -> Value:
    last: Value = NIL
    for arg in raw_args:
        last = interp.eval_form(arg)
    return last


def loop(raw_args: list, interp) -> Value:
    if len(raw_args) < 2:
        raise PlannerRuntimeError("LOOP: нужны x, l и тело")
    param_node = raw_args[0]
    if not isinstance(param_node, IdentNode):
        raise PlannerRuntimeError("LOOP: первый аргумент должен быть именем переменной")
    param_name = param_node.name
    body_nodes = raw_args[2:]
    lst = interp.eval_form(raw_args[1])
    if not hasattr(lst, 'elements'):
        raise PlannerRuntimeError("LOOP: второй аргумент должен быть списком")
    if not lst.elements:
        return NIL
    interp.env.push_frame([param_name], {})
    try:
        last_val: Value = NIL
        for elem in lst.elements:
            interp.env.set_local(param_name, elem)
            for body_expr in body_nodes:
                last_val = interp.eval_form(body_expr)
        return last_val
    finally:
        interp.env.pop_frame()


def for_(raw_args: list, interp) -> Value:
    if len(raw_args) < 2:
        raise PlannerRuntimeError("FOR: нужны x, n и тело")
    param_node = raw_args[0]
    if not isinstance(param_node, IdentNode):
        raise PlannerRuntimeError("FOR: первый аргумент должен быть именем переменной")
    param_name = param_node.name
    body_nodes = raw_args[2:]
    n_val = interp.eval_form(raw_args[1])
    if not isinstance(n_val, (int, float)):
        raise PlannerRuntimeError("FOR: второй аргумент должен быть числом")
    n = int(round(n_val))
    if n < 1:
        return NIL
    interp.env.push_frame([param_name], {})
    try:
        last_val: Value = NIL
        for i in range(1, n + 1):
            interp.env.set_local(param_name, i)
            for body_expr in body_nodes:
                last_val = interp.eval_form(body_expr)
        return last_val
    finally:
        interp.env.pop_frame()


def while_(raw_args: list, interp) -> Value:
    if not raw_args:
        raise PlannerRuntimeError("WHILE: нужны условие и тело")
    pred_node  = raw_args[0]
    body_nodes = raw_args[1:]
    while _is_true(interp.eval_form(pred_node)):
        for body_expr in body_nodes:
            interp.eval_form(body_expr)
    return NIL


def until(raw_args: list, interp) -> Value:
    if not raw_args:
        raise PlannerRuntimeError("UNTIL: нужны тело и условие")
    body_nodes = raw_args[:-1]
    pred_node  = raw_args[-1]
    while True:
        for body_expr in body_nodes:
            interp.eval_form(body_expr)
        if _is_true(interp.eval_form(pred_node)):
            break
    return NIL


def register(interp) -> None:
    interp._fsubrs["DO"]    = lambda raw: do_(raw, interp)
    interp._fsubrs["LOOP"]  = lambda raw: loop(raw, interp)
    interp._fsubrs["FOR"]   = lambda raw: for_(raw, interp)
    interp._fsubrs["WHILE"] = lambda raw: while_(raw, interp)
    interp._fsubrs["UNTIL"] = lambda raw: until(raw, interp)
