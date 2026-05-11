from src.interpreter.functions.backtracking import register_bt
from src.interpreter.functions.fsubr import register_fsubrs
from src.interpreter.functions.spec import (
    PlannerFunction, SimpleParam, ListParams, ParamSpec,
)
from src.interpreter.functions.subr import register_subrs


__all__ = [
    "PlannerFunction", "SimpleParam", "ListParams", "ParamSpec",
]

def register_all(interp) -> None:
    register_subrs(interp)
    register_fsubrs(interp)
    register_bt(interp)
