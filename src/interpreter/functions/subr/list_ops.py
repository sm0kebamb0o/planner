from src.interpreter.values import NIL, T, PlannerList, BracketKind, Value
from src.interpreter.signals import PlannerRuntimeError


def elem(args: list, interp) -> Value:
    interp._check_arity("ELEM", args, 2)
    n   = interp._as_int("ELEM", args[0])
    lst = interp._as_list("ELEM", args[1])
    ln  = len(lst.elements)
    if n == 0 or abs(n) > ln:
        raise PlannerRuntimeError(f"ELEM: индекс {n} за пределами списка длины {ln}")
    idx = (n - 1) if n > 0 else (ln + n)
    return lst.elements[idx]


def index(args: list, interp) -> Value:
    if len(args) < 2:
        raise PlannerRuntimeError("INDEX: нужны список и хотя бы один индекс")
    result: Value = args[0]
    for n_val in args[1:]:
        result = elem([n_val, result], interp)
    return result


def rest(args: list, interp) -> Value:
    interp._check_arity("REST", args, 2)
    n   = interp._as_int("REST", args[0])
    lst = interp._as_list("REST", args[1])
    ln  = len(lst.elements)
    if abs(n) > ln:
        raise PlannerRuntimeError(f"REST: |n|={abs(n)} превышает длину списка {ln}")
    new_elems = lst.elements[n:] if n >= 0 else lst.elements[:ln + n]
    return PlannerList(elements=new_elems, kind=lst.kind)


def head(args: list, interp) -> Value:
    interp._check_arity("HEAD", args, 2)
    n   = interp._as_int("HEAD", args[0])
    lst = interp._as_list("HEAD", args[1])
    ln  = len(lst.elements)
    if abs(n) > ln:
        raise PlannerRuntimeError(f"HEAD: |n|={abs(n)} превышает длину списка {ln}")
    new_elems = lst.elements[:n] if n >= 0 else lst.elements[ln + n:]
    return PlannerList(elements=new_elems, kind=lst.kind)


def length(args: list, interp) -> Value:
    interp._check_arity("LENGTH", args, 1)
    return len(interp._as_list("LENGTH", args[0]).elements)


def memb(args: list, interp) -> Value:
    interp._check_arity("MEMB", args, 2)
    e   = args[0]
    lst = interp._as_list("MEMB", args[1])
    for i, elem_ in enumerate(lst.elements, start=1):
        if elem_ == e:
            return i
    return NIL


def fin(args: list, interp) -> Value:
    interp._check_arity("FIN", args, 2)
    i1, i2 = args[0], args[1]
    if not isinstance(i1, str) or not isinstance(i2, str):
        raise PlannerRuntimeError("FIN: аргументы должны быть именами переменных")
    lst = interp.env.get_local(i2)
    if isinstance(lst, PlannerList) and lst.elements:
        interp._record_undo_local(i1)
        interp._record_undo_local(i2)
        interp.env.set_local(i1, lst.elements[0])
        interp.env.set_local(i2, PlannerList(elements=lst.elements[1:], kind=lst.kind))
        return NIL
    return T


def register(interp) -> None:
    interp._subrs["ELEM"]   = lambda args: elem(args, interp)
    interp._subrs["INDEX"]  = lambda args: index(args, interp)
    interp._subrs["REST"]   = lambda args: rest(args, interp)
    interp._subrs["HEAD"]   = lambda args: head(args, interp)
    interp._subrs["LENGTH"] = lambda args: length(args, interp)
    interp._subrs["MEMB"]   = lambda args: memb(args, interp)
    interp._subrs["FIN"]    = lambda args: fin(args, interp)
