from src.interpreter.models.values import NIL, T, PlannerList, BracketKind, ScaleValue, _is_true, Value


def _bool(cond: bool) -> Value:
    return T if cond else NIL


def id_(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], str))


def num(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], (int, float)) and not isinstance(args[0], bool))


def int_(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], int) and not isinstance(args[0], bool))


def real(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], float))


def scale(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], ScaleValue))


def atom(args: list) -> Value:
    return _bool(len(args) == 1 and not isinstance(args[0], PlannerList))


def list_(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], PlannerList) and args[0].kind == BracketKind.ROUND)


def listr(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], PlannerList))


def listp(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], PlannerList) and args[0].kind == BracketKind.SQUARE)


def lists(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], PlannerList) and args[0].kind == BracketKind.ANGLE)


def empty(args: list) -> Value:
    return _bool(len(args) == 1 and isinstance(args[0], PlannerList) and len(args[0].elements) == 0)


def var(args: list) -> Value:
    return NIL


def not_(args: list) -> Value:
    if len(args) == 1:
        return T if not _is_true(args[0]) else NIL
    return NIL


def register(interp) -> None:
    interp._subrs["ID"]     = id_
    interp._subrs["NUM"]    = num
    interp._subrs["INT"]    = int_
    interp._subrs["REAL"]   = real
    interp._subrs["SCALE"]  = scale
    interp._subrs["ATOM"]   = atom
    interp._subrs["ATOMIC"] = atom
    interp._subrs["LIST"]   = list_
    interp._subrs["LISTR"]  = listr
    interp._subrs["LISTP"]  = listp
    interp._subrs["LISTS"]  = lists
    interp._subrs["EMPTY"]  = empty
    interp._subrs["VAR"]    = var
    interp._subrs["NOT"]    = not_
