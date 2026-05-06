from src.interpreter.models.values import NIL, T, Value
from src.interpreter.models.signals import PlannerRuntimeError


def set_(args: list, interp) -> Value:
    interp._check_arity("SET", args, 2)
    name = args[0]
    if not isinstance(name, str):
        raise PlannerRuntimeError(
            f"SET: первый аргумент должен быть именем переменной, "
            f"получено {interp._repr_value(name)!r}"
        )
    interp._record_undo_local(name)
    interp.env.set_local(name, args[1])
    return args[1]


def cset(args: list, interp) -> Value:
    interp._check_arity("CSET", args, 2)
    if not isinstance(args[0], str):
        raise PlannerRuntimeError("CSET: первый аргумент должен быть именем")
    interp._record_undo_constant(args[0])
    interp.env.set_constant(args[0], args[1])
    return args[1]


def add1(args: list, interp) -> Value:
    interp._check_arity("ADD1", args, 1)
    name = args[0]
    if not isinstance(name, str):
        raise PlannerRuntimeError("ADD1: аргумент должен быть именем переменной")
    val = interp.env.get_local(name)
    new_val = interp._as_number("ADD1", val) + 1
    new_val = int(new_val) if isinstance(val, int) else float(new_val)
    interp._record_undo_local(name)
    interp.env.set_local(name, new_val)
    return new_val


def sub1(args: list, interp) -> Value:
    interp._check_arity("SUB1", args, 1)
    name = args[0]
    if not isinstance(name, str):
        raise PlannerRuntimeError("SUB1: аргумент должен быть именем переменной")
    val = interp.env.get_local(name)
    new_val = interp._as_number("SUB1", val) - 1
    new_val = int(new_val) if isinstance(val, int) else float(new_val)
    interp._record_undo_local(name)
    interp.env.set_local(name, new_val)
    return new_val


def bound(args: list, interp) -> Value:
    interp._check_arity("BOUND", args, 1)
    if not isinstance(args[0], str):
        raise PlannerRuntimeError("BOUND: аргумент должен быть именем")
    return T if interp.env.is_bound(args[0]) else NIL


def hasval(args: list, interp) -> Value:
    interp._check_arity("HASVAL", args, 1)
    if not isinstance(args[0], str):
        raise PlannerRuntimeError("HASVAL: аргумент должен быть именем")
    return T if interp.env.has_value(args[0]) else NIL


def unassign(args: list, interp) -> Value:
    interp._check_arity("UNASSIGN", args, 1)
    if not isinstance(args[0], str):
        raise PlannerRuntimeError("UNASSIGN: аргумент должен быть именем")
    interp.env.unassign(args[0])
    return args[0]


def value(args: list, interp) -> Value:
    interp._check_arity("VALUE", args, 1)
    if not isinstance(args[0], str):
        raise PlannerRuntimeError("VALUE: аргумент должен быть именем переменной")
    return interp.env.get_local(args[0])


def register(interp) -> None:
    interp._subrs["SET"]      = lambda args: set_(args, interp)
    interp._subrs["CSET"]     = lambda args: cset(args, interp)
    interp._subrs["ADD1"]     = lambda args: add1(args, interp)
    interp._subrs["SUB1"]     = lambda args: sub1(args, interp)
    interp._subrs["BOUND"]    = lambda args: bound(args, interp)
    interp._subrs["HASVAL"]   = lambda args: hasval(args, interp)
    interp._subrs["UNASSIGN"] = lambda args: unassign(args, interp)
    interp._subrs["VALUE"]    = lambda args: value(args, interp)
