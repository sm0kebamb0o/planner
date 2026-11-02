from src.interpreter.functions.spec import PlannerFunction, SimpleParam, ListParams, parse_param_spec
from src.interpreter.functions import codec
from src.interpreter.functions.matching.core import match_bt
from src.interpreter.control_flow import EvalStream
from src.interpreter.values import PlannerList, BracketKind
from src.interpreter.errors import PlannerRuntimeError
from src.parser.ast.nodes import IdentNode, LListNode


def define(raw_args: list, interp) -> EvalStream:
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

    params = parse_param_spec(var_node)

    if keyword.name == "LAMBDA":
        interp._functions[fn_name] = PlannerFunction(name=fn_name, params=params, body=body_node)
    elif keyword.name == "KAPPA":
        interp._matchers[fn_name] = _make_kappa_matcher(fn_name, params, body_node, interp)
    else:
        raise PlannerRuntimeError("DEFINE: ожидается ключевое слово LAMBDA или KAPPA")

    yield fn_name


def _make_kappa_matcher(fn_name, params, body, interp):
    def matcher(raw_args, expr):
        if isinstance(params, SimpleParam):
            if params.unevaluated:
                bound_val = PlannerList(
                    elements=[codec.ast_to_value(a) for a in raw_args],
                    kind=BracketKind.ROUND,
                )
            else:
                bound_val = PlannerList(
                    elements=(yield from interp._eval_first_args_bt(raw_args)),
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
                    bindings[pname] = (yield from interp.eval_first_bt(arg_node))
        else:
            raise PlannerRuntimeError("KAPPA: неверная спецификация параметров")

        interp.env.push_frame(declared, bindings)
        try:
            return (yield from match_bt(body, expr, interp))
        finally:
            interp.env.pop_frame()

    return matcher


def register(interp) -> None:
    interp._bt_fsubrs["DEFINE"] = lambda raw: define(raw, interp)
