from src.interpreter.models.values import NIL, Value
from src.interpreter.models.signals import PlannerRuntimeError, PlannerFailure
from src.parser.ast_nodes import LListNode, IdentNode


def prog(raw_args: list, interp) -> Value:
    if not raw_args:
        raise PlannerRuntimeError("PROG: отсутствует список переменных")

    var_list_node = raw_args[0]
    body_nodes    = raw_args[1:]

    if not isinstance(var_list_node, LListNode):
        raise PlannerRuntimeError("PROG: первый аргумент должен быть L-списком переменных")

    declared_names = []
    init_bindings  = {}

    for decl in var_list_node.elements:
        if isinstance(decl, IdentNode):
            declared_names.append(decl.name)
        elif isinstance(decl, LListNode) and len(decl.elements) == 2:
            name_node = decl.elements[0]
            if not isinstance(name_node, IdentNode):
                raise PlannerRuntimeError(
                    f"PROG: имя переменной должно быть идентификатором, получено {name_node!r}"
                )
            declared_names.append(name_node.name)
            init_bindings[name_node.name] = interp.eval_form(decl.elements[1])
        else:
            raise PlannerRuntimeError(f"PROG: неверное объявление переменной: {decl!r}")

    labels = {}
    for i, node in enumerate(body_nodes):
        if isinstance(node, IdentNode):
            labels[node.name] = i

    gen = interp._eval_prog_bt(declared_names, init_bindings, labels, body_nodes)
    try:
        return next(gen)
    except StopIteration:
        raise PlannerFailure(message=interp._last_failure or NIL)


def register(interp) -> None:
    interp._fsubrs["PROG"] = lambda raw: prog(raw, interp)
