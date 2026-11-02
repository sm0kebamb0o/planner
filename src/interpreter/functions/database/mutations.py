from __future__ import annotations

from src.interpreter.database import property_map
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions.database.utils import (
    _assertion, _options, _else, _test,
)
from src.interpreter.functions.utils import check_arity
from src.interpreter.values import NIL, PlannerList


def _assert(args, interp, permanent):
    name = "PASSERT" if permanent else "ASSERT"
    check_arity(name, args, 1, 4)
    options = _options(name, args[1:], {"WITH", "ELSE"})
    value = _assertion((yield from interp.eval_first_bt(args[0])))
    properties = property_map(PlannerList(
        (yield from interp._eval_first_args_bt(options.get("WITH", [])))
    ))
    db = interp.database
    entry = db.insert(value, properties)
    if entry is None:
        return (yield from _else(options, interp))
    if not permanent:
        interp._trail.push_undo(lambda: db.remove(entry.id))
    return entry.value



def _load(args, interp, with_properties):
    name = "DB" if with_properties else "DATA"
    if not args or (with_properties and len(args) % 2):
        raise PlannerRuntimeError(f"{name}: неверное количество аргументов")
    result = NIL
    step = 2 if with_properties else 1
    for i in range(0, len(args), step):
        value = _assertion((yield from interp.eval_first_bt(args[i])))
        result = (yield from interp.eval_first_bt(args[i + 1])) if with_properties else NIL
        properties = property_map(result)
        entry = interp.database.insert(value, properties)
        if not with_properties:
            result = entry.value if entry is not None else NIL
    return result



def _erase(args, interp, permanent):
    name = "PERASE" if permanent else "ERASE"
    check_arity(name, args, 1, 4)
    options = _options(name, args[1:], {"TEST", "ELSE"})
    value = _assertion((yield from interp.eval_first_bt(args[0])))
    db = interp.database
    entry = db.find(value)
    if entry is None or not (yield from _test(entry.properties, options.get("TEST", []), interp)):
        return (yield from _else(options, interp))
    # TEST может выполнять процедуры, поэтому используем данные фактически удалённой записи.
    removed = db.remove(entry.id)
    if removed is None:
        return (yield from _else(options, interp))
    if not permanent:
        interp._trail.push_undo(lambda: db.restore(removed))
    return removed.value

