from src.interpreter.values import NIL, T, PlannerList, Value
from src.interpreter.signals import PlannerRuntimeError


def pset(args: list, interp) -> Value:
    if len(args) != 2:
        raise PlannerRuntimeError("PSET: нужно два аргумента")
    name, val = args
    if not isinstance(name, str):
        raise PlannerRuntimeError("PSET: первый аргумент — имя переменной")
    interp.env.set_local(name, val)
    return val


def padd1(args: list, interp) -> Value:
    if len(args) != 1 or not isinstance(args[0], str):
        raise PlannerRuntimeError("PADD1: нужно имя переменной")
    name = args[0]
    val  = interp.env.get_local(name)
    if isinstance(val, int):
        new_val = val + 1
    elif isinstance(val, float):
        new_val = val + 1.0
    else:
        raise PlannerRuntimeError("PADD1: переменная должна быть числом")
    interp.env.set_local(name, new_val)
    return new_val


def psub1(args: list, interp) -> Value:
    if len(args) != 1 or not isinstance(args[0], str):
        raise PlannerRuntimeError("PSUB1: нужно имя переменной")
    name = args[0]
    val  = interp.env.get_local(name)
    if isinstance(val, int):
        new_val = val - 1
    elif isinstance(val, float):
        new_val = val - 1.0
    else:
        raise PlannerRuntimeError("PSUB1: переменная должна быть числом")
    interp.env.set_local(name, new_val)
    return new_val


def pfin(args: list, interp) -> Value:
    if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
        raise PlannerRuntimeError("PFIN: нужны два имени переменных")
    i1, i2 = args
    lst = interp.env.get_local(i2)
    if isinstance(lst, PlannerList) and lst.elements:
        interp.env.set_local(i1, lst.elements[0])
        interp.env.set_local(i2, PlannerList(elements=lst.elements[1:], kind=lst.kind))
        return NIL
    return T


def pcset(args: list, interp) -> Value:
    if len(args) != 2 or not isinstance(args[0], str):
        raise PlannerRuntimeError("PCSET: первый аргумент — имя константы")
    interp.env.set_constant(args[0], args[1])
    return args[1]


def register(interp) -> None:
    interp._subrs["PSET"]  = lambda args: pset(args, interp)
    interp._subrs["PADD1"] = lambda args: padd1(args, interp)
    interp._subrs["PSUB1"] = lambda args: psub1(args, interp)
    interp._subrs["PFIN"]  = lambda args: pfin(args, interp)
    interp._subrs["PCSET"] = lambda args: pcset(args, interp)
