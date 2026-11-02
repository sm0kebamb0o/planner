from src.interpreter.control_flow import EvalStream
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions import codec
from src.parser.ast.nodes import LListNode


def quote(raw_args: list) -> EvalStream:
    if len(raw_args) != 1:
        raise PlannerRuntimeError("QUOTE: ожидается ровно один аргумент")
    yield codec.ast_to_value(raw_args[0])


def form(raw_args: list, interp):
    yield from interp._eval_llist(LListNode(elements=raw_args))


def register(interp) -> None:
    interp._bt_fsubrs["QUOTE"] = quote
    interp._bt_fsubrs["FORM"]  = lambda raw: form(raw, interp)
