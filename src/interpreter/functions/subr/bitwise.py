from src.interpreter.values import ScaleValue, Value
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions.utils import as_int, as_scale, check_arity


def bitor(args: list, interp) -> Value:
    check_arity("BITOR", args, 2)
    s1 = as_scale("BITOR", args[0], float_digits=interp._float_digits)
    s2 = as_scale("BITOR", args[1], float_digits=interp._float_digits)
    bits = s1.bits | s2.bits
    return ScaleValue(bits=bits, source=oct(bits)[2:])


def bitand(args: list, interp) -> Value:
    check_arity("BITAND", args, 2)
    s1 = as_scale("BITAND", args[0], float_digits=interp._float_digits)
    s2 = as_scale("BITAND", args[1], float_digits=interp._float_digits)
    bits = s1.bits & s2.bits
    return ScaleValue(bits=bits, source=oct(bits)[2:])


def comp(args: list, interp) -> Value:
    check_arity("COMP", args, 2)
    s1 = as_scale("COMP", args[0], float_digits=interp._float_digits)
    s2 = as_scale("COMP", args[1], float_digits=interp._float_digits)
    bits = s1.bits ^ s2.bits
    return ScaleValue(bits=bits, source=oct(bits)[2:])


def shift(args: list, interp) -> Value:
    check_arity("SHIFT", args, 2)
    s = as_scale("SHIFT", args[0], float_digits=interp._float_digits)
    n = as_int("SHIFT", args[1], float_digits=interp._float_digits)
    bits = (s.bits >> n) if n >= 0 else (s.bits << (-n))
    return ScaleValue(bits=bits, source=oct(bits)[2:])


def bsum(args: list, interp) -> Value:
    check_arity("BSUM", args, 1)
    return bin(as_scale("BSUM", args[0], float_digits=interp._float_digits).bits).count("1")


def topbit(args: list, interp) -> Value:
    check_arity("TOPBIT", args, 1)
    return as_scale("TOPBIT", args[0], float_digits=interp._float_digits).bits.bit_length()


def register(interp) -> None:
    interp._subrs["BITOR"]    = lambda args: bitor(args, interp)
    interp._subrs["BITAND"]    = lambda args: bitand(args, interp)
    interp._subrs["COMP"]   = lambda args: comp(args, interp)
    interp._subrs["SHIFT"]  = lambda args: shift(args, interp)
    interp._subrs["BSUM"]   = lambda args: bsum(args, interp)
    interp._subrs["TOPBIT"] = lambda args: topbit(args, interp)
