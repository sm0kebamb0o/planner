from src.interpreter.functions.spec import PlannerFunction, SimpleParam, ListParams
from src.interpreter.functions import codec
from src.interpreter.values import Value, PlannerList, BracketKind
from src.interpreter.signals import PlannerRuntimeError
from src.parser.ast.nodes import IdentNode, LListNode


def define(raw_args: list, interp) -> Value:
    if len(raw_args) != 2:
        raise PlannerRuntimeError(
            "DEFINE: ожидается ровно два аргумента: имя и LAMBDA/KAPPA-выражение"
        )
    fn_name_node = raw_args[0]
    if not isinstance(fn_name_node, IdentNode):
        raise PlannerRuntimeError("DEFINE: первый аргумент должен быть идентификатором")
    fn_name = fn_name_node.name

    lambda_node = raw_args[1]
    if not isinstance(lambda_node, LListNode) or len(lambda_node.elements) != 3:
        raise PlannerRuntimeError("DEFINE: второй аргумент должен быть (LAMBDA/KAPPA var body)")

    keyword, var_node, body_node = lambda_node.elements
    if not isinstance(keyword, IdentNode) or keyword.name not in ("LAMBDA", "KAPPA"):
        raise PlannerRuntimeError("DEFINE: ожидается ключевое слово LAMBDA или KAPPA")

    params = interp._parse_param_spec(var_node)

    if keyword.name == "LAMBDA":
        interp._functions[fn_name] = PlannerFunction(name=fn_name, params=params, body=body_node)
    else:  # KAPPA
        interp._matchers[fn_name] = _make_kappa_matcher(fn_name, params, body_node, interp)

    return fn_name


def _make_kappa_matcher(fn_name, params, body, interp):
    """Создать замыкание-сопоставитель для KAPPA-определения."""
    from src.interpreter.functions.matching import match

    def matcher(raw_args, expr, interp_):
        if isinstance(params, SimpleParam):
            if params.unevaluated:
                bound_val = PlannerList(
                    elements=[codec.ast_to_value(a) for a in raw_args],
                    kind=BracketKind.ROUND,
                )
            else:
                bound_val = PlannerList(
                    elements=[interp_.eval_form(a) for a in raw_args],
                    kind=BracketKind.ROUND,
                )
            declared = [params.name]
            bindings = {params.name: bound_val}
        elif isinstance(params, ListParams):
            if len(params.params) != len(raw_args):
                raise PlannerRuntimeError(
                    f"Сопоставитель '{fn_name}': ожидалось "
                    f"{len(params.params)} аргументов, получено {len(raw_args)}"
                )
            declared = [name for name, _ in params.params]
            bindings = {}
            for (pname, unevaluated), arg_node in zip(params.params, raw_args):
                if unevaluated:
                    bindings[pname] = codec.ast_to_value(arg_node)
                else:
                    bindings[pname] = interp_.eval_form(arg_node)
        else:
            raise PlannerRuntimeError("KAPPA: неверная спецификация параметров")

        interp_.env.push_frame(declared, bindings)
        try:
            return match(body, expr, interp_)
        finally:
            interp_.env.pop_frame()

    return matcher


def register(interp) -> None:
    interp._fsubrs["DEFINE"] = lambda raw: define(raw, interp)
