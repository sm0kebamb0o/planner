from src.interpreter.models.values import NIL, _is_true, Value
from src.interpreter.models.signals import PlannerRuntimeError
from src.parser.ast.nodes import LListNode


def cond(raw_args: list, interp) -> Value:
    for clause_node in raw_args:
        if not isinstance(clause_node, LListNode):
            raise PlannerRuntimeError(
                f"COND: клауза должна быть списком, получено {clause_node!r}"
            )
        clause = clause_node.elements
        if not clause:
            raise PlannerRuntimeError("COND: пустая клауза")
        cond_val = interp.eval_form(clause[0])
        if _is_true(cond_val):
            if len(clause) == 1:
                return cond_val
            last: Value = NIL
            for body_expr in clause[1:]:
                last = interp.eval_form(body_expr)
            return last
    return NIL


def register(interp) -> None:
    interp._fsubrs["COND"] = lambda raw: cond(raw, interp)
