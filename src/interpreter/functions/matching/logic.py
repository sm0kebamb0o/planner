from __future__ import annotations

from src.parser.ast.nodes import LListNode, IdentNode
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions.matching.core import match


def _non(args, expr, interp):
    if not args:
        raise PlannerRuntimeError("NON: нужен образец")
    mark = interp._trail.mark()
    result = match(args[0], expr, interp)
    interp._trail.undo_to(mark)
    return not result


def register(matchers: dict, interp) -> None:

    matchers["NON"] = _non

    def _et(args, expr, interp):
        for pat in args:
            mark = interp._trail.mark()
            if not match(pat, expr, interp):
                interp._trail.undo_to(mark)
                return False
        return True

    matchers["ET"] = _et

    def _same(args, expr, interp):
        if not args:
            raise PlannerRuntimeError("SAME: нужен список переменных")
        vars_node = args[0]
        pat_args = args[1:]
        if not isinstance(vars_node, LListNode):
            raise PlannerRuntimeError("SAME: первый аргумент — список переменных")
        local_names = [
            n.name for n in vars_node.elements
            if isinstance(n, IdentNode)
        ]
        interp.env.push_frame(local_names, {})
        try:
            return _et(pat_args, expr, interp)
        finally:
            interp.env.pop_frame()

    matchers["SAME"] = _same

    def _aut(args, expr, interp):
        for pat in args:
            mark = interp._trail.mark()
            if match(pat, expr, interp):
                return True
            interp._trail.undo_to(mark)
        return False

    matchers["AUT"] = _aut

    def _when(args, expr, interp):
        for clause_node in args:
            if not isinstance(clause_node, LListNode) or not clause_node.elements:
                raise PlannerRuntimeError("WHEN: клауза должна быть списком")
            cond_pat = clause_node.elements[0]
            body_pats = clause_node.elements[1:]
            mark = interp._trail.mark()
            if match(cond_pat, expr, interp):
                for bp in body_pats:
                    if not match(bp, expr, interp):
                        interp._trail.undo_to(mark)
                        return False
                return True
            interp._trail.undo_to(mark)
        return False

    matchers["WHEN"] = _when
