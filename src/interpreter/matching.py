"""Сопоставление образцов (IS) и встроенные сопоставители для Плэнера.

Функция match(pat, expr, interp) рекурсивно сопоставляет образец pat
с вычисленным значением expr.  При успехе переменные образца получают
значения (через трейл, чтобы откат FAIL их восстановил).  При неудаче
caller обязан вызвать trail.undo_to(mark), сохранённый до вызова match.

Посегментное сопоставление L-списков реализует полный backtracking:
левый !*X получает минимальный возможный сегмент; при неудаче дальше
по образцу сегмент расширяется на один элемент.
"""
from __future__ import annotations

import operator as _op

from src.parser.ast.nodes import (
    FormNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)
from src.interpreter.trail import _UNBOUND
from src.interpreter.models.values import NIL, T, BracketKind, PlannerList, ScaleValue, _is_true
from src.interpreter.models.signals import PlannerRuntimeError


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------


def _bind(name: str, val: "Value", interp: "PlannerInterpreter") -> None:
    """Связать переменную val через трейл."""
    if interp.env.has_value(name):
        old = interp.env.get_local(name)
        interp._trail.push_undo(lambda n=name, o=old: interp.env.set_local(n, o))
    else:
        interp._trail.push_undo(lambda n=name: interp.env.unassign(n))
    interp.env.set_local(name, val)


def _is_segmented(pat: FormNode) -> bool:
    """True если образец является сегментным (начинается с !)."""
    if isinstance(pat, VarRefNode):
        return pat.segmented
    if isinstance(pat, CallNode):
        return pat.segmented   # <g args> и <>
    return False


# ---------------------------------------------------------------------------
# Основная функция сопоставления
# ---------------------------------------------------------------------------

def match(pat: FormNode, expr: "Value",
          interp: "PlannerInterpreter") -> bool:
    """Сопоставить образец pat с вычисленным значением expr.

    Возвращает True при успехе (с побочным эффектом: переменные образца
    связаны через трейл).  При неудаче возвращает False без отката —
    caller должен вызвать trail.undo_to(mark).
    """
    # --- Атомарные образцы ---
    if isinstance(pat, IdentNode):
        return expr == pat.name

    if isinstance(pat, IntNode):
        return expr == pat.value

    if isinstance(pat, FloatNode):
        return expr == pat.value

    if isinstance(pat, ScaleNode):
        return (isinstance(expr, ScaleValue) and expr.bits == pat.bits)

    # --- Переменные образца ---
    if isinstance(pat, VarRefNode) and not pat.segmented:
        if pat.mode == VarMode.ASSIGN:       # *X — всегда связывает
            _bind(pat.name, expr, interp)
            return True

        if pat.mode == VarMode.READ:         # .X — проверяет или связывает
            if interp.env.has_value(pat.name):
                return interp.env.get_local(pat.name) == expr
            _bind(pat.name, expr, interp)
            return True

        if pat.mode == VarMode.CONST:        # :C — проверяет константу
            if not interp.env.has_constant(pat.name):
                return False
            return interp.env.get_constant(pat.name) == expr

    # --- Образец-список (только простые элементы без сегментных) ---
    if isinstance(pat, LListNode):
        if not isinstance(expr, PlannerList) or expr.kind != BracketKind.ROUND:
            return False
        # Если в списке нет сегментных образцов — простое поэлементное
        if not any(_is_segmented(p) for p in pat.elements):
            if len(pat.elements) != len(expr.elements):
                return False
            for p, e in zip(pat.elements, expr.elements):
                if not match(p, e, interp):
                    return False
            return True
        # Есть сегментные — используем алгоритм с backtracking
        return match_list(pat.elements, expr.elements, 0, 0, interp)

    # --- [] или <> — пустые wildcards без аргументов (§5.3) ---
    if isinstance(pat, CallNode) and not pat.args and isinstance(pat.head, IdentNode) and not pat.head.name:
        return True

    # --- Обращение к сопоставителю [matcher ...] ---
    if isinstance(pat, CallNode) and isinstance(pat.head, IdentNode):
        matcher_name = pat.head.name
        if matcher_name in interp._matchers:
            return interp._matchers[matcher_name](pat.args, expr, interp)
        # Вычислить как обычное выражение и проверить равенство
        val = interp.eval_form(pat)
        return val == expr

    # --- Fallback: вычислить образец и сравнить ---
    try:
        val = interp.eval_form(pat)
        return val == expr
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Посегментное сопоставление
# ---------------------------------------------------------------------------

def match_list(
    pats: list[FormNode],
    items: list["Value"],
    pi: int,
    ii: int,
    interp: "PlannerInterpreter",
) -> bool:
    """Рекурсивный алгоритм сопоставления списка-образца с сегментными элементами.

    pats  — элементы образца-списка
    items — элементы сопоставляемого списка
    pi    — текущий индекс в pats
    ii    — текущий индекс в items
    """
    # Базовый случай: всё совпало
    if pi == len(pats) and ii == len(items):
        return True

    # Образцы кончились, но элементы ещё есть — неудача
    if pi == len(pats):
        return False

    # Элементы кончились, но образцы ещё есть
    if ii == len(items):
        # Успех только если все оставшиеся образцы — свободные wildcards
        return _all_wildcards(pats, pi, items, ii, interp)

    pat = pats[pi]

    if _is_segmented(pat):
        return _match_segment(pat, pats, items, pi, ii, interp)
    else:
        mark = interp._trail.mark()
        if match(pat, items[ii], interp):
            if match_list(pats, items, pi + 1, ii + 1, interp):
                return True
        interp._trail.undo_to(mark)
        return False


def _try_bind_segment(
    seg_pat: FormNode,
    seg_list: "PlannerList",
    interp: "PlannerInterpreter",
) -> bool:
    """Попытаться связать seg_list с сегментным образцом.

    Возвращает True при успехе (с возможным побочным эффектом на трейле).
    Не выполняет откат при неудаче — это делает вызывающая сторона.
    """
    if isinstance(seg_pat, VarRefNode):
        if seg_pat.mode == VarMode.ASSIGN:    # !*X — всегда связывает
            _bind(seg_pat.name, seg_list, interp)
            return True
        if seg_pat.mode == VarMode.READ:      # !.X
            if interp.env.has_value(seg_pat.name):
                return interp.env.get_local(seg_pat.name) == seg_list
            _bind(seg_pat.name, seg_list, interp)
            return True
        if seg_pat.mode == VarMode.CONST:     # !:C
            if interp.env.has_constant(seg_pat.name):
                return interp.env.get_constant(seg_pat.name) == seg_list
            return False

    if isinstance(seg_pat, CallNode) and seg_pat.segmented:
        if not seg_pat.args:
            # <> — сегментный wildcard без привязки; соответствует любому сегменту
            return True
        # <g args> — вызвать сопоставитель с сегментом как значением
        if isinstance(seg_pat.head, IdentNode):
            name = seg_pat.head.name
            if name in interp._matchers:
                return interp._matchers[name](seg_pat.args, seg_list, interp)
        return False

    return False


def _match_segment(
    seg_pat: FormNode,
    pats: list[FormNode],
    items: list["Value"],
    pi: int,
    ii: int,
    interp: "PlannerInterpreter",
) -> bool:
    """Перебрать длины сегмента от 0 до максимума, ища успешное продолжение."""
    max_remaining = len(items) - ii
    # Посчитать минимально необходимое число элементов для оставшихся несегментных
    min_needed = sum(1 for p in pats[pi + 1:] if not _is_segmented(p))
    max_seg_len = max_remaining - min_needed

    for seg_len in range(0, max_seg_len + 1):
        mark = interp._trail.mark()
        segment = items[ii: ii + seg_len]
        seg_list = PlannerList(elements=list(segment), kind=BracketKind.ROUND)

        if _try_bind_segment(seg_pat, seg_list, interp):
            if match_list(pats, items, pi + 1, ii + seg_len, interp):
                return True

        interp._trail.undo_to(mark)

    return False


def _all_wildcards(
    pats: list[FormNode],
    pi: int,
    items: list["Value"],
    ii: int,
    interp: "PlannerInterpreter",
) -> bool:
    """Все оставшиеся образцы — свободные сегментные wildcards → bind пустые."""
    empty = PlannerList(elements=[], kind=BracketKind.ROUND)
    for p in pats[pi:]:
        if not _is_segmented(p):
            return False
        if isinstance(p, VarRefNode):
            if p.mode == VarMode.ASSIGN:
                _bind(p.name, empty, interp)
            elif p.mode == VarMode.READ:
                if interp.env.has_value(p.name):
                    if interp.env.get_local(p.name) != empty:
                        return False
                else:
                    _bind(p.name, empty, interp)
            elif p.mode == VarMode.CONST:
                if not interp.env.has_constant(p.name):
                    return False
                if interp.env.get_constant(p.name) != empty:
                    return False
        elif isinstance(p, CallNode) and p.segmented:
            if not p.args:
                pass  # <> — wildcard, пустой сегмент всегда успешен
            else:
                # <g args> — вызвать сопоставитель с пустым списком
                if isinstance(p.head, IdentNode) and p.head.name in interp._matchers:
                    if not interp._matchers[p.head.name](p.args, empty, interp):
                        return False
                else:
                    return False
        else:
            return False
    return True


# ---------------------------------------------------------------------------
# Встроенные сопоставители
# ---------------------------------------------------------------------------

def _make_matchers(interp) -> dict:
    """Создать словарь встроенных сопоставителей."""
    def _bool(cond: bool):
        return T if cond else NIL

    matchers: dict = {}

    # --- Типовые сопоставители (без аргументов) ---

    def _type_matcher(name: str, predicate):
        def fn(args, expr, interp):
            return predicate(expr)
        matchers[name] = fn

    _type_matcher("ID",     lambda e: isinstance(e, str))
    _type_matcher("NUM",    lambda e: isinstance(e, (int, float)) and not isinstance(e, bool))
    _type_matcher("INT",    lambda e: isinstance(e, int) and not isinstance(e, bool))
    _type_matcher("REAL",   lambda e: isinstance(e, float))
    _type_matcher("SCALE",  lambda e: isinstance(e, ScaleValue))
    _type_matcher("ATOM",   lambda e: not isinstance(e, PlannerList))
    _type_matcher("ATOMIC", lambda e: not isinstance(e, PlannerList))

    def _list_matcher(args, expr, interp):
        if not isinstance(expr, PlannerList) or expr.kind != BracketKind.ROUND:
            return False
        if args:
            return match(args[0], len(expr.elements), interp)
        return True

    matchers["LIST"] = _list_matcher

    def _listp_matcher(args, expr, interp):
        if not isinstance(expr, PlannerList) or expr.kind != BracketKind.SQUARE:
            return False
        if args:
            return match(args[0], len(expr.elements), interp)
        return True

    matchers["LISTP"] = _listp_matcher

    def _lists_matcher(args, expr, interp):
        if not isinstance(expr, PlannerList) or expr.kind != BracketKind.ANGLE:
            return False
        if args:
            return match(args[0], len(expr.elements), interp)
        return True

    matchers["LISTS"] = _lists_matcher

    def _listr_matcher(args, expr, interp):
        if not isinstance(expr, PlannerList):
            return False
        if args:
            return match(args[0], len(expr.elements), interp)
        return True

    matchers["LISTR"] = _listr_matcher

    # --- VAR-сопоставители (§5.1) ---
    # Переменная-ссылка в позиции значения — 1-элементный L-список с строкой-префиксом.
    # Например, [QUOTE .X] → (".X"), [QUOTE !*Y] → ("!*Y").

    def _var_ref_check(prefix: str):
        def check(expr) -> bool:
            return (
                isinstance(expr, PlannerList) and
                expr.kind == BracketKind.ROUND and
                len(expr.elements) == 1 and
                isinstance(expr.elements[0], str) and
                expr.elements[0].startswith(prefix) and
                len(expr.elements[0]) > len(prefix)
            )
        return check

    _vdot  = _var_ref_check(".")
    _vstar = _var_ref_check("*")
    _vcol  = _var_ref_check(":")
    _vsdot = _var_ref_check("!.")
    _vsstr = _var_ref_check("!*")
    _vscol = _var_ref_check("!:")

    _type_matcher("VAR.",  _vdot)
    _type_matcher("VAR*",  _vstar)
    _type_matcher("VAR:",  _vcol)
    _type_matcher("VAR!.", _vsdot)
    _type_matcher("VAR!*", _vsstr)
    _type_matcher("VAR!:", _vscol)
    _type_matcher("VARP",  lambda e: _vdot(e) or _vstar(e) or _vcol(e))
    _type_matcher("VARS",  lambda e: _vsdot(e) or _vsstr(e) or _vscol(e))
    _type_matcher("VAR",   lambda e: _vdot(e) or _vstar(e) or _vcol(e) or
                                      _vsdot(e) or _vsstr(e) or _vscol(e))

    # --- Числовые сопоставители ---

    def _num_cmp(op):
        def fn(args, expr, interp):
            if not args or not isinstance(expr, (int, float)):
                return False
            n = interp.eval_form(args[0])
            if not isinstance(n, (int, float)):
                return False
            return op(expr, n)
        return fn

    matchers["LT"] = _num_cmp(_op.lt)
    matchers["LE"] = _num_cmp(_op.le)
    matchers["GT"] = _num_cmp(_op.gt)
    matchers["GE"] = _num_cmp(_op.ge)

    # --- Логические сопоставители ---

    def _non_matcher(args, expr, interp):
        """NON pat — соответствует если pat НЕ соответствует."""
        if not args:
            raise PlannerRuntimeError("NON: нужен образец")
        mark = interp._trail.mark()
        result = match(args[0], expr, interp)
        # В любом случае откатить побочные эффекты
        interp._trail.undo_to(mark)
        return not result

    matchers["NON"] = _non_matcher

    def _et_matcher(args, expr, interp):
        """ET pat1 pat2 ... — конъюнкция."""
        for pat in args:
            mark = interp._trail.mark()
            if not match(pat, expr, interp):
                interp._trail.undo_to(mark)
                return False
        return True

    matchers["ET"] = _et_matcher

    def _same_matcher(args, expr, interp):
        """SAME (v1 v2 ...) pat1 pat2 ... — как ET с локальными переменными."""
        if not args:
            raise PlannerRuntimeError("SAME: нужен список переменных")
        vars_node = args[0]
        pat_args = args[1:]
        if not isinstance(vars_node, LListNode):
            raise PlannerRuntimeError("SAME: первый аргумент — список переменных")
        local_names = [
            n.name for n in vars_node.elements
            if isinstance(n, IdentNode)
        ]
        interp.env.push_frame(local_names, {})
        try:
            return _et_matcher(pat_args, expr, interp)
        finally:
            interp.env.pop_frame()

    matchers["SAME"] = _same_matcher

    def _aut_matcher(args, expr, interp):
        """AUT pat1 pat2 ... — дизъюнкция (первый успешный)."""
        for pat in args:
            mark = interp._trail.mark()
            if match(pat, expr, interp):
                return True
            interp._trail.undo_to(mark)
        return False

    matchers["AUT"] = _aut_matcher

    def _when_matcher(args, expr, interp):
        """WHEN (cond body...) ... — условный сопоставитель."""
        for clause_node in args:
            if not isinstance(clause_node, LListNode) or not clause_node.elements:
                raise PlannerRuntimeError("WHEN: клауза должна быть списком")
            cond_pat = clause_node.elements[0]
            body_pats = clause_node.elements[1:]
            mark = interp._trail.mark()
            if match(cond_pat, expr, interp):
                # Условие подошло — применить тело (ET)
                for bp in body_pats:
                    if not match(bp, expr, interp):
                        interp._trail.undo_to(mark)
                        return False
                return True
            interp._trail.undo_to(mark)
        return False

    matchers["WHEN"] = _when_matcher

    # --- Специальные сопоставители ---

    def _be_matcher(args, expr, interp):
        """BE e — вычислить e; если () → неудача, иначе успех (expr игнорируется)."""
        if not args:
            raise PlannerRuntimeError("BE: нужен аргумент")
        val = interp.eval_form(args[0])
        return val != NIL and _is_true(val)

    matchers["BE"] = _be_matcher

    def _pat_matcher(args, expr, interp):
        """PAT e — вычислить e → образец, применить match."""
        if not args:
            raise PlannerRuntimeError("PAT: нужен аргумент")
        pat_val = interp.eval_form(args[0])
        pat_node = interp._value_to_form(pat_val)
        return match(pat_node, expr, interp)

    matchers["PAT"] = _pat_matcher

    def _one_of_matcher(args, expr, interp):
        """ONE-OF l — expr входит в список l."""
        if not args:
            raise PlannerRuntimeError("ONE-OF: нужен список")
        lst = interp.eval_form(args[0])
        if not isinstance(lst, PlannerList):
            raise PlannerRuntimeError("ONE-OF: аргумент должен быть списком")
        return expr in lst.elements

    matchers["ONE-OF"] = _one_of_matcher

    def _has_matcher(args, expr, interp):
        """HAS ind pat ... — идентификатор со свойствами."""
        if not isinstance(expr, str):
            return False
        if len(args) % 2 != 0:
            raise PlannerRuntimeError("HAS: нужны пары ind pat")
        for i in range(0, len(args), 2):
            ind_val = interp.eval_form(args[i])
            pat_node = args[i + 1]
            if not isinstance(ind_val, str):
                return False
            # Свойства идентификаторов хранятся через PUT — пока нет поддержки
            # TODO: интегрировать с таблицей свойств когда она появится
            return False
        return True

    matchers["HAS"] = _has_matcher

    def _linear_matcher(args, expr, interp):
        """LINEAR pat... — как образец-список, для любых скобок."""
        if not isinstance(expr, PlannerList):
            return False
        if not any(_is_segmented(p) for p in args):
            if len(args) != len(expr.elements):
                return False
            for p, e in zip(args, expr.elements):
                if not match(p, e, interp):
                    return False
            return True
        return match_list(args, expr.elements, 0, 0, interp)

    matchers["LINEAR"] = _linear_matcher

    def _star_matcher(args, expr, interp):
        """STAR pat — список, все элементы соответствуют pat."""
        if not isinstance(expr, PlannerList) or not args:
            return False
        pat = args[0]
        for elem in expr.elements:
            mark = interp._trail.mark()
            if not match(pat, elem, interp):
                interp._trail.undo_to(mark)
                return False
        return True

    matchers["STAR"] = _star_matcher

    return matchers


# ---------------------------------------------------------------------------
# Регистрация IS и сопоставителей
# ---------------------------------------------------------------------------

def register_all(interp) -> None:
    """Зарегистрировать IS и все встроенные сопоставители."""
    # Заполнить таблицу сопоставителей
    interp._matchers.update(_make_matchers(interp))

    # IS — FSUBR: первый аргумент (образец) не вычисляется
    def fsubr_is(raw_args):
        if len(raw_args) != 2:
            raise PlannerRuntimeError("IS: ожидается образец и выражение")
        pat_node, expr_node = raw_args
        expr = interp.eval_form(expr_node)
        mark = interp._trail.mark()
        if match(pat_node, expr, interp):
            return T
        interp._trail.undo_to(mark)
        return NIL

    interp._fsubrs["IS"] = fsubr_is
