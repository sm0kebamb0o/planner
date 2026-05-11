import src.interpreter.functions.subr.arithmetic as arithmetic
import src.interpreter.functions.subr.bitwise as bitwise
import src.interpreter.functions.subr.comparison as comparison
import src.interpreter.functions.subr.control as control
import src.interpreter.functions.subr.io as io
import src.interpreter.functions.subr.list_ops as list_ops
import src.interpreter.functions.subr.math_fns as math_fns
import src.interpreter.functions.subr.predicates as predicates
import src.interpreter.functions.subr.variables as variables


def register_subrs(interp) -> None:
    arithmetic.register(interp)
    math_fns.register(interp)
    bitwise.register(interp)
    list_ops.register(interp)
    predicates.register(interp)
    comparison.register(interp)
    variables.register(interp)
    control.register(interp)
    io.register(interp)
