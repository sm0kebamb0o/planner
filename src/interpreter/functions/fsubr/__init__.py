from . import logic, cond, prog, loops, define, quote


def register_fsubrs(interp) -> None:
    logic.register(interp)
    cond.register(interp)
    prog.register(interp)
    loops.register(interp)
    define.register(interp)
    quote.register(interp)
