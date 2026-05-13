import math

from src.interpreter.values import Value
from src.interpreter.errors import PlannerRuntimeError


def register(interp) -> None:
    _math = [
        ("SIN",    math.sin),
        ("COS",    math.cos),
        ("TG",     math.tan),
        ("CTG",    lambda x: 1.0 / math.tan(x)),
        ("ARCSIN", math.asin),
        ("ARCCOS", math.acos),
        ("ARCTG",  math.atan),
        ("EXP",    math.exp),
        ("LN",     math.log),
    ]
    for name, impl in _math:
        def _make(n, fn):
            def _f(args: list) -> Value:
                interp._check_arity(n, args, 1)
                return fn(float(interp._as_number(n, args[0])))
            return _f
        interp._subrs[name] = _make(name, impl)
