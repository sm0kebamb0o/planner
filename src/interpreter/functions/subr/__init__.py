from . import arithmetic, math_fns, bitwise, list_ops, predicates, comparison, variables, control, io


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
