from . import among, alt, fail, gate, if_, perm_strg_temp, xprog, find, permanent


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
