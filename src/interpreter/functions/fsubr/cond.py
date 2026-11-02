from src.interpreter.control_flow import EvalStream

from src.interpreter.values import NIL, _is_true, Value
from src.interpreter.errors import PlannerRuntimeError
from src.parser.ast.nodes import LListNode


def cond(raw_args: list, interp) -> EvalStream:
    for clause_node in raw_args:
        if not isinstance(clause_node, LListNode):
            raise PlannerRuntimeError(
                f"COND: клауза должна быть списком, получено {clause_node!r}"
            )
        clause = clause_node.elements
        if not clause:
            raise PlannerRuntimeError("COND: пустая клауза")
        cond_val = (yield from interp.eval_first_bt(clause[0]))
        if _is_true(cond_val):
            if len(clause) == 1:
                yield cond_val
                return
            last: Value = NIL
            # Здесь возможны возвраты
            for body_expr in clause[1:]:
                last = (yield from interp.eval_first_bt(body_expr))
            yield last
            return
    yield NIL


def register(interp) -> None:
    interp._bt_fsubrs["COND"] = lambda raw: cond(raw, interp)
