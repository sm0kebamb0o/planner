import math

from src.interpreter.values import Value
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.functions.utils import as_number, check_arity


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
                check_arity(n, args, 1)
                return fn(float(as_number(n, args[0], float_digits=interp._float_digits)))
            return _f
        interp._subrs[name] = _make(name, impl)
