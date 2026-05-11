import src.interpreter.functions.backtracking.alt as alt
import src.interpreter.functions.backtracking.among as among
import src.interpreter.functions.backtracking.fail as fail
import src.interpreter.functions.backtracking.find as find
import src.interpreter.functions.backtracking.gate as gate
import src.interpreter.functions.backtracking.if_ as if_
import src.interpreter.functions.backtracking.permanent as permanent
import src.interpreter.functions.backtracking.perm_strg_temp as perm_strg_temp
import src.interpreter.functions.backtracking.xprog as xprog


def register_bt(interp) -> None:
    among.register(interp)
    alt.register(interp)
    fail.register(interp)
    gate.register(interp)
    if_.register(interp)
    perm_strg_temp.register(interp)
    xprog.register(interp)
    find.register(interp)
    permanent.register(interp)
