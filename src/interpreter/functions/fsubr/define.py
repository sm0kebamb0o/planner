from src.interpreter.models.values import Value
from src.interpreter.models.signals import PlannerRuntimeError
from src.interpreter.models.functions import PlannerFunction
from src.parser.ast_nodes import IdentNode, LListNode


def define(raw_args: list, interp) -> Value:
    if len(raw_args) != 2:
        raise PlannerRuntimeError(
            "DEFINE: ожидается ровно два аргумента: имя и LAMBDA-выражение"
        )
    fn_name_node = raw_args[0]
    if not isinstance(fn_name_node, IdentNode):
        raise PlannerRuntimeError("DEFINE: первый аргумент должен быть идентификатором")
    fn_name = fn_name_node.name

    lambda_node = raw_args[1]
    if not isinstance(lambda_node, LListNode) or len(lambda_node.elements) != 3:
        raise PlannerRuntimeError("DEFINE: второй аргумент должен быть (LAMBDA var body)")

    keyword, var_node, body_node = lambda_node.elements
    if not isinstance(keyword, IdentNode) or keyword.name != "LAMBDA":
        raise PlannerRuntimeError("DEFINE: ожидается ключевое слово LAMBDA")

    params = interp._parse_param_spec(var_node)
    interp._functions[fn_name] = PlannerFunction(name=fn_name, params=params, body=body_node)
    return fn_name


def register(interp) -> None:
    interp._fsubrs["DEFINE"] = lambda raw: define(raw, interp)
