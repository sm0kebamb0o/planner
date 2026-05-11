import src.interpreter.functions.fsubr.cond as cond
import src.interpreter.functions.fsubr.define as define
import src.interpreter.functions.fsubr.logic as logic
import src.interpreter.functions.fsubr.loops as loops
import src.interpreter.functions.fsubr.prog as prog
import src.interpreter.functions.fsubr.quote as quote


def register_fsubrs(interp) -> None:
    logic.register(interp)
    cond.register(interp)
    prog.register(interp)
    loops.register(interp)
    define.register(interp)
    quote.register(interp)
