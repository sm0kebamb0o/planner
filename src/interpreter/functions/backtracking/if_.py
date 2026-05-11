from src.interpreter.values import NIL, Value
from src.interpreter.signals import PlannerFailure, PlannerRuntimeError
from src.parser.ast.nodes import LListNode


def if_(raw_args: list, interp) -> Value:
    """IF (cond1 e11 ... e1m) (cond2 ...) ... — условный с F-точкой."""
    for clause_node in raw_args:
        if not isinstance(clause_node, LListNode) or not clause_node.elements:
            raise PlannerRuntimeError("IF: клауза должна быть непустым списком")

        cond_node  = clause_node.elements[0]
        body_nodes = clause_node.elements[1:]
        mark = interp._trail.mark()

        try:
            cond_val = interp.eval_form(cond_node)
            interp._trail.discard_to(mark)
            if not body_nodes:
                return cond_val
            val: Value = NIL
            for node in body_nodes:
                val = interp.eval_form(node)
            return val
        except PlannerFailure as f:
            interp._trail.undo_to(mark)
            if f.target is not None:
                raise
            continue

    return NIL


def register(interp) -> None:
    interp._fsubrs["IF"] = lambda raw: if_(raw, interp)
