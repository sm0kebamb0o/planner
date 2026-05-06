from .subr import register_subrs
from .fsubr import register_fsubrs
from .backtracking import register_bt


def register_all(interp) -> None:
    register_subrs(interp)
    register_fsubrs(interp)
    register_bt(interp)
