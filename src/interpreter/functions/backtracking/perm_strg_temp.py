from src.interpreter.functions.backtracking.utils import _close_forks_since
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.signals import PlannerFailure
from src.interpreter.values import Value
from src.parser.ast.nodes import IdentNode


def _parse_label(raw_args: list):
    """Вернуть (label_or_None, expr_node)."""
    if len(raw_args) >= 2 and isinstance(raw_args[0], IdentNode):
        return raw_args[0].name, raw_args[1]
    return None, raw_args[0]


def perm(raw_args: list, interp) -> Value:
    """PERM [label] e — уничтожить F-точки И обратные операторы внутри e."""
    if not raw_args:
        raise PlannerRuntimeError("PERM: нужен аргумент")
    label, expr_node = _parse_label(raw_args)
    depth = len(interp._fork_stack)
    mark  = interp._trail.mark()
    try:
        val = interp.eval_form(expr_node)
    except PlannerFailure as f:
        _close_forks_since(interp, depth)
        if label is not None and f.target == label:
            raise PlannerFailure(message=f.message)
        raise
    _close_forks_since(interp, depth)
    interp._trail.discard_to(mark)
    return val


def strg(raw_args: list, interp) -> Value:
    """STRG [label] e — уничтожить только F-точки; обратные операторы сохранить."""
    if not raw_args:
        raise PlannerRuntimeError("STRG: нужен аргумент")
    label, expr_node = _parse_label(raw_args)
    depth = len(interp._fork_stack)
    try:
        val = interp.eval_form(expr_node)
    except PlannerFailure as f:
        _close_forks_since(interp, depth)
        if label is not None and f.target == label:
            raise PlannerFailure(message=f.message)
        raise
    _close_forks_since(interp, depth)
    return val


def temp(raw_args: list, interp) -> Value:
    """TEMP [label] e — уничтожить F-точки И откатить обратные операторы."""
    if not raw_args:
        raise PlannerRuntimeError("TEMP: нужен аргумент")
    label, expr_node = _parse_label(raw_args)
    depth = len(interp._fork_stack)
    mark  = interp._trail.mark()
    try:
        val = interp.eval_form(expr_node)
    except PlannerFailure as f:
        _close_forks_since(interp, depth)
        interp._trail.undo_to(mark)
        if label is not None and f.target == label:
            raise PlannerFailure(message=f.message)
        raise
    _close_forks_since(interp, depth)
    interp._trail.undo_to(mark)
    return val


def cleanup_perm(interp, depth: int, mark) -> None:
    _close_forks_since(interp, depth)
    interp._trail.discard_to(mark)


def cleanup_strg(interp, depth: int, mark) -> None:
    _close_forks_since(interp, depth)


def cleanup_temp(interp, depth: int, mark) -> None:
    _close_forks_since(interp, depth)
    interp._trail.undo_to(mark)


def register(interp) -> None:
    interp._fsubrs["PERM"] = lambda raw: perm(raw, interp)
    interp._fsubrs["STRG"] = lambda raw: strg(raw, interp)
    interp._fsubrs["TEMP"] = lambda raw: temp(raw, interp)
