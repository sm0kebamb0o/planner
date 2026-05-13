from src.interpreter.values import PlannerList, BracketKind, Value
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions import codec
from src.parser.ast.nodes import VarRefNode, VarMode, CallNode


def quote(raw_args: list) -> Value:
    if len(raw_args) != 1:
        raise PlannerRuntimeError("QUOTE: ожидается ровно один аргумент")
    return codec.ast_to_value(raw_args[0])


def form(raw_args: list, interp) -> Value:
    result = []
    for arg in raw_args:
        if isinstance(arg, VarRefNode) and arg.segmented:
            raw_v = (
                interp.env.get_local(arg.name)
                if arg.mode == VarMode.READ
                else interp.env.get_constant(arg.name)
            )
            result.extend(interp._segment(raw_v))
        elif isinstance(arg, CallNode) and arg.segmented:
            raw_v = interp._eval_call(arg.head, arg.args)
            result.extend(interp._segment(raw_v))
        else:
            result.append(interp.eval_form(arg))
    return PlannerList(elements=result, kind=BracketKind.ROUND)


def register(interp) -> None:
    interp._fsubrs["QUOTE"] = quote
    interp._fsubrs["FORM"]  = lambda raw: form(raw, interp)
