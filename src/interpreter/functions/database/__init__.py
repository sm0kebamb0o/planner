from src.interpreter.functions.database.mutations import _assert, _load, _erase
from src.interpreter.functions.database.output import _dump
from src.interpreter.functions.database.properties import _geta, _puta
from src.interpreter.functions.database.search import _search, _candidates
from src.interpreter.functions.database.utils import _one


def register(interp):
    for name, permanent in (("ASSERT", False), ("PASSERT", True)):
        interp._bt_fsubrs[name] = lambda args, p=permanent: _one(lambda: _assert(args, interp, p), interp)
    for name, permanent in (("ERASE", False), ("PERASE", True)):
        interp._bt_fsubrs[name] = lambda args, p=permanent: _one(lambda: _erase(args, interp, p), interp)
    interp._bt_fsubrs["DATA"] = lambda args: _one(lambda: _load(args, interp, False), interp)
    interp._bt_fsubrs["DB"] = lambda args: _one(lambda: _load(args, interp, True), interp)
    interp._bt_fsubrs["SEARCH"] = lambda args: _search(args, interp)
    interp._bt_fsubrs["SEARCH1"] = lambda args: _search(args, interp, True)
    interp._bt_fsubrs["CANDIDATES"] = lambda args: _candidates(args, interp)
    interp._subrs["GETA"] = lambda args: _geta(args, interp)
    interp._subrs["PUTA"] = lambda args: _puta(args, interp, False)
    interp._subrs["PPUTA"] = lambda args: _puta(args, interp, True)
    interp._subrs["DUMP"] = lambda args: _dump(args, interp)

