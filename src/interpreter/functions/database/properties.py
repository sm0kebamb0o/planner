from __future__ import annotations

from copy import deepcopy

from src.interpreter.database import property_list
from src.interpreter.functions.database.utils import _assertion
from src.interpreter.functions.utils import as_ident, check_arity
from src.interpreter.signals import PlannerFailure
from src.interpreter.values import NIL


def _geta(args, interp):
    check_arity("GETA", args, 1, 2)
    value = _assertion(args[0])
    name = as_ident(args[1], float_digits=interp._float_digits) if len(args) == 2 else None
    entry = interp.database.find(value)
    if entry is None:
        raise PlannerFailure("GETA")
    return property_list(entry.properties) if name is None else deepcopy(entry.properties.get(name, NIL))



def _puta(args, interp, permanent):
    fn = "PPUTA" if permanent else "PUTA"
    check_arity(fn, args, 3)
    value = _assertion(args[0])
    name = as_ident(args[1], float_digits=interp._float_digits)
    db = interp.database
    entry = db.find(value)
    if entry is None:
        raise PlannerFailure(fn)
    if not permanent:
        old = deepcopy(entry.properties.get(name, NIL))
        interp._trail.push_undo(lambda: db.set_property(entry.id, name, old))
    db.set_property(entry.id, name, args[2])
    return args[2]

