from src.interpreter.values import ScaleValue, Value
from src.interpreter.signals import PlannerRuntimeError


def bitor(args: list, interp) -> Value:
    interp._check_arity("\\/", args, 2)
    s1 = interp._as_scale("\\/", args[0])
    s2 = interp._as_scale("\\/", args[1])
    bits = s1.bits | s2.bits
    return ScaleValue(bits=bits, source=oct(bits)[2:])


def bitand(args: list, interp) -> Value:
    interp._check_arity("/\\", args, 2)
    s1 = interp._as_scale("/\\", args[0])
    s2 = interp._as_scale("/\\", args[1])
    bits = s1.bits & s2.bits
    return ScaleValue(bits=bits, source=oct(bits)[2:])


def comp(args: list, interp) -> Value:
    interp._check_arity("COMP", args, 2)
    s1 = interp._as_scale("COMP", args[0])
    s2 = interp._as_scale("COMP", args[1])
    bits = s1.bits ^ s2.bits
    return ScaleValue(bits=bits, source=oct(bits)[2:])


def shift(args: list, interp) -> Value:
    interp._check_arity("SHIFT", args, 2)
    s = interp._as_scale("SHIFT", args[0])
    n = interp._as_int("SHIFT", args[1])
    bits = (s.bits >> n) if n >= 0 else (s.bits << (-n))
    return ScaleValue(bits=bits, source=oct(bits)[2:])


def bsum(args: list, interp) -> Value:
    interp._check_arity("BSUM", args, 1)
    return bin(interp._as_scale("BSUM", args[0]).bits).count("1")


def topbit(args: list, interp) -> Value:
    interp._check_arity("TOPBIT", args, 1)
    return interp._as_scale("TOPBIT", args[0]).bits.bit_length()


def register(interp) -> None:
    interp._subrs["\\/"]    = lambda args: bitor(args, interp)
    interp._subrs["/\\"]    = lambda args: bitand(args, interp)
    interp._subrs["COMP"]   = lambda args: comp(args, interp)
    interp._subrs["SHIFT"]  = lambda args: shift(args, interp)
    interp._subrs["BSUM"]   = lambda args: bsum(args, interp)
    interp._subrs["TOPBIT"] = lambda args: topbit(args, interp)
