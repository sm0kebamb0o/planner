from src.interpreter.values import NIL, Value
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.signals import PlannerFailure
from src.interpreter.control_flow import EvalStream, ControlExhausted
from src.parser.ast.nodes import LListNode


def if_(raw_args: list, interp) -> EvalStream:
    """IF (cond1 e11 ... e1m) (cond2 ...) ... — условный с F-точкой."""
    for clause_node in raw_args:
        if not isinstance(clause_node, LListNode) or not clause_node.elements:
            raise PlannerRuntimeError("IF: клауза должна быть непустым списком")

        cond_node  = clause_node.elements[0]
        body_nodes = clause_node.elements[1:]
        mark = interp._trail.mark()

        try:
            cond_val = (yield from interp.eval_first_bt(cond_node))
            interp._trail.discard_to(mark)
            if not body_nodes:
                yield cond_val
                return
            val: Value = NIL
            for node in body_nodes:
                val = (yield from interp.eval_first_bt(node))
            yield val
            return
        except PlannerFailure as f:
            if isinstance(f, ControlExhausted):
                raise
            interp._trail.undo_to(mark)
            if f.target is not None:
                raise
            continue

    yield NIL


def register(interp) -> None:
    interp._bt_fsubrs["IF"] = lambda raw: if_(raw, interp)
