from __future__ import annotations

from functools import lru_cache

from src.interpreter.database import property_list
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions import codec
from src.interpreter.functions.database.utils import _options, _pattern, _test
from src.interpreter.functions.matching.core import match_bt, _is_segmented
from src.interpreter.functions.utils import check_arity
from src.interpreter.signals import PlannerFailure
from src.interpreter.values import BracketKind, PlannerList
from src.parser.ast.nodes import FloatNode, IdentNode, IntNode, LListNode, ScaleNode


def _search(args, interp, first_only=False):
    name = "SEARCH1" if first_only else "SEARCH"
    check_arity(name, args, 1, 2)
    options = _options(name, args[1:], {"TEST"})
    pattern = _pattern(args[0], interp)
    db = interp.database
    ids = db.ids()

    for record_id in ids:
        entry = db.get(record_id)
        if entry is None:
            continue
        mark = interp._trail.mark()
        try:
            accepted = (yield from match_bt(pattern, entry.value, interp))
            # Сопоставление может изменить базу; проверяем текущие свойства записи.
            current = db.get(record_id)
            accepted = (accepted and current is not None
                        and (yield from _test(current.properties, options.get("TEST", []), interp)))
        except PlannerFailure as failure:
            interp._trail.undo_to(mark)
            if failure.target is not None:
                raise
            accepted = False
        except GeneratorExit:
            raise
        except BaseException:
            interp._trail.undo_to(mark)
            raise
        if accepted:
            yield entry.value
        interp._trail.undo_to(mark)
        if accepted and first_only:
            break
    interp._last_failure = name


def _partial(pattern, value):
    pats = pattern.elements
    items = value.elements

    def compatible(pat, item):
        if isinstance(pat, (IdentNode, IntNode, FloatNode, ScaleNode)):
            return codec.ast_to_value(pat) == item
        if isinstance(pat, LListNode):
            return (isinstance(item, PlannerList) and item.kind == BracketKind.ROUND
                    and (any(_is_segmented(p) for p in pat.elements)
                         or len(pat.elements) == len(item.elements)))
        return True

    @lru_cache(None)
    def walk(pi, ii):
        if pi == len(pats):
            return ii == len(items)
        if _is_segmented(pats[pi]):
            return any(walk(pi + 1, j) for j in range(ii, len(items) + 1))
        return (ii < len(items) and compatible(pats[pi], items[ii])
                and walk(pi + 1, ii + 1))

    return walk(0, 0)


def _candidates(args, interp):
    check_arity("CANDIDATES", args, 1, 2)
    if len(args) == 2 and (yield from interp.eval_first_bt(args[1])) != "ASSERT":
        raise PlannerRuntimeError("CANDIDATES: пока поддерживается только тип ASSERT")
    pattern = _pattern(args[0], interp)
    elements = []
    for record_id in interp.database.ids():
        entry = interp.database.get(record_id)
        if entry is not None and _partial(pattern, entry.value):
            elements.extend([entry.value, property_list(entry.properties)])
    yield PlannerList(elements)

