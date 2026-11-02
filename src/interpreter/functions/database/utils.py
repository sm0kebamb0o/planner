from __future__ import annotations

from copy import deepcopy

from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions import codec
from src.interpreter.functions.matching.core import match_bt, _is_segmented
from src.interpreter.signals import PlannerFailure
from src.interpreter.values import BracketKind, NIL, PlannerList
from src.parser.ast.nodes import IdentNode, LListNode, VarMode, VarRefNode
from src.interpreter.functions.utils import as_ident


def _assertion(value):
    if not isinstance(value, PlannerList) or value.kind != BracketKind.ROUND:
        raise PlannerRuntimeError("База данных: утверждение должно быть L-списком")
    return value



def _options(name, nodes, allowed):
    result = {}
    for node in nodes:
        if not (isinstance(node, LListNode) and node.elements
                and isinstance(node.elements[0], IdentNode)):
            raise PlannerRuntimeError(f"{name}: ожидается аргумент WITH, TEST или ELSE")
        tag = node.elements[0].name
        if tag in {"USE", "USE1", "TRY", "FILTER"}:
            raise PlannerRuntimeError(f"{name}: рекомендации и теоремы пока не поддерживаются")
        if tag not in allowed or tag in result:
            raise PlannerRuntimeError(f"{name}: недопустимый или повторный аргумент {tag}")
        items = node.elements[1:]
        if tag in {"WITH", "TEST"} and (not items or len(items) % 2):
            raise PlannerRuntimeError(f"{name}: {tag} требует пары имя/значение")
        if tag == "ELSE" and len(items) > 1:
            raise PlannerRuntimeError(f"{name}: ELSE принимает не более одной формы")
        result[tag] = items
    return result



def _else(options, interp):
    if "ELSE" not in options:
        return NIL
    if not options["ELSE"]:
        raise PlannerFailure()
    return (yield from interp.eval_first_bt(options["ELSE"][0]))



def _test(properties, items, interp):
    mark = interp._trail.mark()
    try:
        for name_node, pattern in zip(items[::2], items[1::2]):
            name = as_ident((yield from interp.eval_first_bt(name_node)), float_digits=interp._float_digits)
            if _is_segmented(pattern):
                raise PlannerRuntimeError("TEST: требуется простой образец")
            if not (yield from match_bt(pattern, deepcopy(properties.get(name, NIL)), interp)):
                interp._trail.undo_to(mark)
                return False
        return True
    except GeneratorExit:
        raise
    except BaseException:
        interp._trail.undo_to(mark)
        raise



def _pattern(node, interp):
    if isinstance(node, VarRefNode) and node.mode == VarMode.READ and not node.segmented:
        node = codec.value_to_pattern(interp.env.get_local(node.name))
    if not isinstance(node, LListNode):
        raise PlannerRuntimeError("Поиск: образец должен быть L-списком или .переменной")
    return node



def _one(operation, interp):
    mark = interp._trail.mark()
    try:
        result = yield from operation()
        yield result
        interp._trail.undo_to(mark)
    except PlannerFailure as failure:
        interp._trail.undo_to(mark)
        if failure.target is not None:
            raise
        interp._last_failure = failure.message if failure.message is not None else NIL
    except Exception:
        interp._trail.undo_to(mark)
        raise

