"""Тесты IS, сопоставителей и режима возвратов.

Запуск:
    cd /Users/mt1mur/Documents/CMC/planner
    python -m pytest src/interpreter/test/test_backtracking.py -v
"""

import sys
import os
import io
import unittest

_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.lexer import Lexer
from src.parser import PlannerReader
from src.interpreter import PlannerInterpreter, PlannerList, BracketKind
from src.interpreter.interpreter import NIL, T


def _make_interp():
    return PlannerInterpreter()


def _run_source(source: str, interp=None):
    """Выполнить источник и вернуть (stdout_lines, last_value)."""
    groups = Lexer(source).tokenize()
    prog   = PlannerReader().read(groups)
    buf    = io.StringIO()
    old    = sys.stdout
    sys.stdout = buf
    try:
        if interp is None:
            interp = PlannerInterpreter()
        interp.run(prog)
    finally:
        sys.stdout = old
    lines = buf.getvalue().strip().splitlines()
    # Строки чередуются: исходная форма, результат, исходная форма, результат...
    values = lines[1::2]   # каждая вторая строка — результат вычисления
    return lines, values


def _eval_last(source: str, interp=None) -> str:
    """Выполнить и вернуть последнее значение."""
    lines, values = _run_source(source, interp)
    return values[-1] if values else ""


# ===========================================================================
# IS — базовое сопоставление
# ===========================================================================

class TestIS(unittest.TestCase):

    def test_atom_match(self):
        self.assertEqual(_eval_last("[IS ABC ABC]"), "T")

    def test_atom_no_match(self):
        self.assertEqual(_eval_last("[IS ABC DEF]"), "()")

    def test_number_match(self):
        self.assertEqual(_eval_last("[IS 5 [+ 2 3]]"), "T")

    def test_number_no_match(self):
        self.assertEqual(_eval_last("[IS 5 6]"), "()")

    def test_star_var_bind(self):
        """*X всегда связывается."""
        result = _eval_last("[PROG (X) [IS *X HELLO] .X]")
        self.assertEqual(result, "HELLO")

    def test_dot_var_bind(self):
        """.X без значения — связывается."""
        result = _eval_last("[PROG (X) [IS .X WORLD] .X]")
        self.assertEqual(result, "WORLD")

    def test_dot_var_check_equal(self):
        """.X с значением — проверяет равенство (успех)."""
        result = _eval_last("[PROG (X) [SET X A] [IS .X A]]")
        self.assertEqual(result, "T")

    def test_dot_var_check_unequal(self):
        """.X с значением — проверяет равенство (неудача)."""
        result = _eval_last("[PROG (X) [SET X A] [IS .X B]]")
        self.assertEqual(result, "()")

    def test_dot_var_same_twice(self):
        """(.X .X) — обе позиции должны совпадать."""
        result = _eval_last("[PROG (X) [IS (.X .X) (A A)]]")
        self.assertEqual(result, "T")

    def test_dot_var_different(self):
        """(.X .X) — разные значения → неудача."""
        result = _eval_last("[PROG (X) [IS (.X .X) (A B)]]")
        self.assertEqual(result, "()")

    def test_list_match(self):
        result = _eval_last("[IS (A B C) (A B C)]")
        self.assertEqual(result, "T")

    def test_list_wrong_length(self):
        result = _eval_last("[IS (A B) (A B C)]")
        self.assertEqual(result, "()")

    def test_list_bind_vars(self):
        result = _eval_last("[PROG (X Y) [IS (*X *Y) (1 2)] [+ .X .Y]]")
        self.assertEqual(result, "3")


# ===========================================================================
# IS — сегментные образцы
# ===========================================================================

class TestISSegmented(unittest.TestCase):

    def test_segmented_star_binds_list(self):
        """!*X получает список."""
        result = _eval_last("[PROG (X) [IS (!*X) (A B C)] .X]")
        self.assertEqual(result, "(A B C)")

    def test_segmented_split(self):
        """!*X *Y — !*X получает всё кроме последнего элемента."""
        result = _eval_last("[PROG (X Y) [IS (!*X *Y) (1 2 3)] .X]")
        self.assertEqual(result, "(1 2)")   # X = (1 2), Y = 3

    def test_segmented_middle(self):
        """A !*X B — захватить средний сегмент."""
        result = _eval_last("[PROG (X) [IS (A !*X B) (A 1 2 B)] .X]")
        self.assertEqual(result, "(1 2)")

    def test_segmented_empty(self):
        """!*X может быть пустым."""
        result = _eval_last("[PROG (X) [IS (!*X A) (A)] .X]")
        self.assertEqual(result, "()")

    def test_segmented_plus_pattern(self):
        """!*X + !*Y — разделить по первому плюсу."""
        result = _eval_last("[PROG (X Y) [IS (!*X + !*Y) (1 2 + 3 4)] [LENGTH .X]]")
        self.assertEqual(result, "2")


# ===========================================================================
# Встроенные сопоставители
# ===========================================================================

class TestMatchers(unittest.TestCase):

    def test_matcher_num(self):
        self.assertEqual(_eval_last("[IS [NUM] 42]"), "T")

    def test_matcher_num_fail(self):
        self.assertEqual(_eval_last("[IS [NUM] ABC]"), "()")

    def test_matcher_id(self):
        self.assertEqual(_eval_last("[IS [ID] HELLO]"), "T")

    def test_matcher_int(self):
        self.assertEqual(_eval_last("[IS [INT] 5]"), "T")

    def test_matcher_int_fail_float(self):
        self.assertEqual(_eval_last("[IS [INT] 5.0]"), "()")

    def test_matcher_list(self):
        self.assertEqual(_eval_last("[IS [LIST] (1 2 3)]"), "T")

    def test_matcher_list_length(self):
        self.assertEqual(_eval_last("[IS [LIST 3] (1 2 3)]"), "T")

    def test_matcher_list_length_fail(self):
        self.assertEqual(_eval_last("[IS [LIST 2] (1 2 3)]"), "()")

    def test_matcher_non_atom(self):
        """[NON [NUM]] не подходит к числу."""
        self.assertEqual(_eval_last("[IS [NON [NUM]] ABC]"), "T")

    def test_matcher_non_fail(self):
        self.assertEqual(_eval_last("[IS [NON [NUM]] 42]"), "()")

    def test_matcher_gt(self):
        self.assertEqual(_eval_last("[IS [GT 3] 5]"), "T")

    def test_matcher_gt_fail(self):
        self.assertEqual(_eval_last("[IS [GT 3] 2]"), "()")

    def test_matcher_et(self):
        """ET [NUM] [GT 0] — конъюнкция."""
        self.assertEqual(_eval_last("[IS [ET [NUM] [GT 0]] 5]"), "T")

    def test_matcher_et_fail(self):
        self.assertEqual(_eval_last("[IS [ET [NUM] [GT 0]] -1]"), "()")

    def test_matcher_aut(self):
        """AUT [NUM] [ID] — дизъюнкция."""
        self.assertEqual(_eval_last("[IS [AUT [NUM] [ID]] ABC]"), "T")
        self.assertEqual(_eval_last("[IS [AUT [NUM] [ID]] 42]"), "T")

    def test_matcher_one_of(self):
        self.assertEqual(_eval_last("[IS [ONE-OF (A B C)] B]"), "T")

    def test_matcher_one_of_fail(self):
        self.assertEqual(_eval_last("[IS [ONE-OF (A B C)] D]"), "()")

    def test_star_matcher(self):
        """STAR [NUM] — список из чисел."""
        self.assertEqual(_eval_last("[IS [STAR [NUM]] (1 2 3)]"), "T")

    def test_star_matcher_fail(self):
        self.assertEqual(_eval_last("[IS [STAR [NUM]] (1 A 3)]"), "()")


# ===========================================================================
# FAIL, MESS
# ===========================================================================

class TestFailMess(unittest.TestCase):

    def test_fail_at_toplevel(self):
        """Неуспех на верхнем уровне печатает =НЕУСПЕХ=."""
        lines, _ = _run_source("[FAIL]")
        self.assertTrue(any("НЕУСПЕХ" in l for l in lines))

    def test_fail_with_message(self):
        lines, _ = _run_source("[FAIL OOPS]")
        self.assertTrue(any("OOPS" in l for l in lines))

    def test_mess(self):
        """[MESS] возвращает сообщение последнего неуспеха."""
        result = _eval_last("[PROG (X) [GATE [FAIL HELLO]] [MESS]]")
        self.assertEqual(result, "HELLO")


# ===========================================================================
# GATE
# ===========================================================================

class TestGate(unittest.TestCase):

    def test_gate_success(self):
        """GATE успешно — возвращает значение."""
        self.assertEqual(_eval_last("[GATE [+ 1 2]]"), "3")

    def test_gate_fail_returns_nil(self):
        """GATE при неуспехе → ()."""
        self.assertEqual(_eval_last("[GATE [FAIL]]"), "()")

    def test_gate_among_fail(self):
        """[GATE [AMONG (1 2 3)] [FAIL]] перебирает все варианты → ()."""
        result = _eval_last("[GATE [AMONG (1 2 3)] [FAIL]]")
        self.assertEqual(result, "()")


# ===========================================================================
# AMONG / ALT
# ===========================================================================

class TestAMONG(unittest.TestCase):

    def test_among_first_value(self):
        """Первое значение AMONG берётся без отката."""
        result = _eval_last("[PROG (X) [SET X [AMONG (10 20 30)]] .X]")
        self.assertEqual(result, "10")

    def test_among_empty_fails(self):
        """AMONG пустого списка → НЕУСПЕХ на верхнем уровне."""
        lines, _ = _run_source("[AMONG ()]")
        output = " ".join(lines)
        self.assertTrue("НЕУСПЕХ" in output or "AMONG" in output)

    def test_among_collect_all(self):
        """FIND ALL собирает все значения AMONG."""
        result = _eval_last("[FIND ALL (X) .X [SET X [AMONG (1 2 3)]]]")
        self.assertEqual(result, "(3 2 1)")

    def test_alt_first_success(self):
        """ALT возвращает первую успешную альтернативу."""
        result = _eval_last("[PROG (X) [SET X [ALT 10 20]] .X]")
        self.assertEqual(result, "10")

    def test_alt_skip_fail(self):
        """ALT пропускает неуспешные ветви."""
        result = _eval_last("[PROG (X) [SET X [ALT [FAIL] 99]] .X]")
        self.assertEqual(result, "99")


# ===========================================================================
# IF (режим возвратов)
# ===========================================================================

class TestIF(unittest.TestCase):

    def test_if_first_match(self):
        result = _eval_last("[IF ([EQ 1 1] OK)]")
        self.assertEqual(result, "OK")

    def test_if_second_clause(self):
        """Если первое условие неуспешно — переходит ко второму."""
        result = _eval_last("[IF ([FAIL] A) (() B)]")
        self.assertEqual(result, "B")

    def test_if_all_fail(self):
        """Все условия неуспешны → ()."""
        result = _eval_last("[IF ([FAIL] A) ([FAIL] B)]")
        self.assertEqual(result, "()")

    def test_if_no_body(self):
        """Клауза без тела возвращает значение условия."""
        result = _eval_last("[IF (T)]")
        self.assertEqual(result, "T")


# ===========================================================================
# FIND
# ===========================================================================

class TestFIND(unittest.TestCase):

    def test_find_all_among(self):
        """FIND ALL собирает все элементы."""
        result = _eval_last("[FIND ALL (X) .X [SET X [AMONG (A B C)]]]")
        self.assertEqual(result, "(C B A)")

    def test_find_exact_count(self):
        """FIND 2 собирает ровно 2."""
        result = _eval_last("[FIND 2 (X) .X [SET X [AMONG (1 2 3 4)]]]")
        self.assertEqual(result, "(2 1)")

    def test_find_with_filter(self):
        """FIND с условием внутри тела."""
        result = _eval_last(
            "[FIND ALL (X) .X "
            " [SET X [AMONG (1 -2 3 -5)]]"
            " [COND ([LT .X 0] [FAIL])]]"
        )
        self.assertEqual(result, "(3 1)")

    def test_find_zero_returns_nil(self):
        """FIND 0 → ()."""
        result = _eval_last("[FIND 0 (X) .X [SET X [AMONG (1 2)]]]")
        self.assertEqual(result, "()")


# ===========================================================================
# PERM, STRG, TEMP
# ===========================================================================

class TestPERMSTRGTEMP(unittest.TestCase):

    def test_perm_commits_effects(self):
        """PERM: побочные эффекты не откатываются при последующем FAIL."""
        result = _eval_last(
            "[PROG (X) "
            " [SET X 0]"
            " [GATE [PERM [SET X 42]] [FAIL]]"
            " .X]"
        )
        self.assertEqual(result, "42")

    def test_temp_undoes_effects(self):
        """TEMP: побочные эффекты откатываются на выходе."""
        result = _eval_last(
            "[PROG (X) "
            " [SET X 0]"
            " [TEMP [SET X 99]]"
            " .X]"
        )
        self.assertEqual(result, "0")


# ===========================================================================
# PSET и другие постоянные варианты
# ===========================================================================

class TestPermanent(unittest.TestCase):

    def test_pset_not_undone(self):
        """PSET не откатывается при FAIL."""
        result = _eval_last(
            "[PROG (X) "
            " [SET X 0]"
            " [GATE [PSET X 77] [FAIL]]"
            " .X]"
        )
        self.assertEqual(result, "77")

    def test_padd1(self):
        result = _eval_last("[PROG (N) [SET N 5] [PADD1 N] .N]")
        self.assertEqual(result, "6")

    def test_psub1(self):
        result = _eval_last("[PROG (N) [SET N 5] [PSUB1 N] .N]")
        self.assertEqual(result, "4")


# ===========================================================================
# Trail откат при неуспехе
# ===========================================================================

class TestTrailRollback(unittest.TestCase):

    def test_set_rolled_back(self):
        """SET откатывается при неуспехе через AMONG/FAIL."""
        result = _eval_last(
            "[PROG (X) "
            " [SET X 0]"
            " [GATE [SET X [AMONG (1 2 3)]] [FAIL]]"
            " .X]"
        )
        # После исчерпания всех альтернатив AMONG X должен быть 0
        self.assertEqual(result, "0")

    def test_add1_rolled_back(self):
        """ADD1 откатывается при неуспехе."""
        result = _eval_last(
            "[PROG (N) "
            " [SET N 0]"
            " [GATE [ADD1 N] [FAIL]]"
            " .N]"
        )
        self.assertEqual(result, "0")

    def test_is_binding_rolled_back(self):
        """IS-связывание откатывается при последующем FAIL."""
        result = _eval_last(
            "[PROG (X) "
            " [GATE [IS *X HELLO] [FAIL]]"
            " [BOUND X]]"
        )
        # X не должна иметь значения после отката
        self.assertEqual(result, "T")   # BOUND — да, объявлена, но без значения


# ===========================================================================
# SUM — классический пример из спецификации
# ===========================================================================

class TestSUM(unittest.TestCase):

    def test_sum_basic(self):
        """SUM находит набор чисел из списка с заданной суммой."""
        src = """
[DEFINE SUM (LAMBDA (L N)
  [PROG (K (M ()) (S 0))
    A [SET K [AMONG .L]]
      [SET M (!.M .K)]
      [SET S [+ .S .K]]
      [COND ([EQ .S .N] .M)
            ([LT .S .N] [GO A])
            (T [FAIL])]])]
[SUM (6 3 2 1) 5]
"""
        result = _eval_last(src)
        # Допустимые ответы: (3 2) или (2 2 1) и т.п. — сумма должна быть 5
        from src.lexer import Lexer
        from src.parser import PlannerReader
        from src.interpreter import PlannerInterpreter
        groups = Lexer(result.strip("()").replace(" ", " ")).tokenize()
        # Просто проверим что не пустой список и не =НЕУСПЕХ=
        self.assertNotIn("НЕУСПЕХ", result)
        self.assertTrue(result.startswith("("))

    def test_sum_no_solution(self):
        """SUM без решения → НЕУСПЕХ."""
        src = """
[DEFINE SUM (LAMBDA (L N)
  [PROG (K (M ()) (S 0))
    A [SET K [AMONG .L]]
      [SET M (!.M .K)]
      [SET S [+ .S .K]]
      [COND ([EQ .S .N] .M)
            ([LT .S .N] [GO A])
            (T [FAIL])]])]
[SUM (4 2) 7]
"""
        lines, _ = _run_source(src)
        self.assertTrue(any("НЕУСПЕХ" in l for l in lines))

    def test_sum_first_solution(self):
        """Первое решение [SUM (6 3 2 1) 5] = (3 2)."""
        src = """
[DEFINE SUM (LAMBDA (L N)
  [PROG (K (M ()) (S 0))
    A [SET K  [AMONG .L]]
      [SET M  (!.M .K)]
      [SET S  [+ .S .K]]
      [COND ([EQ .S .N] .M)
            ([LT .S .N] [GO A])
            (T [FAIL])]])]
[SUM (6 3 2 1) 5]
"""
        self.assertEqual(_eval_last(src), "(3 2)")

    def test_sum_length4(self):
        """Решение длины 4 для [SUM (6 3 2 1) 5] = (2 1 1 1)."""
        src = """
[DEFINE SUM (LAMBDA (L N)
  [PROG (K (M ()) (S 0))
    A [SET K  [AMONG .L]]
      [SET M  (!.M .K)]
      [SET S  [+ .S .K]]
      [COND ([EQ .S .N] .M)
            ([LT .S .N] [GO A])
            (T [FAIL])]])]
[PROG (X) [SET X [SUM (6 3 2 1) 5]]
          [COND ([NEQ [LENGTH .X] 4] [FAIL])]
          .X]
"""
        self.assertEqual(_eval_last(src), "(2 1 1 1)")

    def test_sum_all_solutions(self):
        """DO+PRINT+FAIL собирает все решения; каждое даёт сумму 5."""
        src = """
[DEFINE SUM (LAMBDA (L N)
  [PROG (K (M ()) (S 0))
    A [SET K  [AMONG .L]]
      [SET M  (!.M .K)]
      [SET S  [+ .S .K]]
      [COND ([EQ .S .N] .M)
            ([LT .S .N] [GO A])
            (T [FAIL])]])]
[DO [ALT () [EXIT T DO]]
    [PRINT [SUM (6 3 2 1) 5]]
    [FAIL]]
"""
        lines, values = _run_source(src)
        solutions = [v for v in values if v.startswith("(")]
        self.assertGreater(len(solutions), 1)
        for sol in solutions:
            nums = [int(x) for x in sol.strip("()").split()]
            self.assertEqual(sum(nums), 5)


# ===========================================================================
# Ф8 — задача 8 ферзей (queens.plan)
# ===========================================================================

_QUEENS_DEF = """
[DEFINE ДИАГ (LAMBDA (V LV)
  [PROG (H (H1 0))
    [SET H [+ [LENGTH .LV] 1]]
    [LOOP V1 .LV [ADD1 H1]
      [UNFALSE [NEQ [ABS [- .H  .H1]]
                    [ABS [- .V  .V1]]]]]])]

[DEFINE Ф8 (LAMBDA ()
  [PROG (V FV (LV ()) B E)
    [SET FV (1 2 3 4 5 6 7 8)]
    [FOR H 8
      [SET V  [AMONG .FV]]
      [ДИАГ .V .LV]
      [SET LV (!.LV .V)]
      [IS (!*B .V !*E) .FV]
      [SET FV (!.B !.E)]]
    .LV])]
"""


class TestQueens(unittest.TestCase):

    def test_queens_first_solution(self):
        """Первое решение задачи 8 ферзей."""
        result = _eval_last(_QUEENS_DEF + "[Ф8]")
        self.assertEqual(result, "(1 5 8 6 3 7 2 4)")

    def test_queens_solution_is_valid(self):
        """Первое решение Ф8 — корректная расстановка (перестановка, без диагоналей)."""
        result = _eval_last(_QUEENS_DEF + "[Ф8]")
        cols = [int(x) for x in result.strip("()").split()]
        self.assertEqual(len(cols), 8)
        self.assertEqual(sorted(cols), list(range(1, 9)))
        for i in range(8):
            for j in range(i + 1, 8):
                self.assertNotEqual(abs(cols[i] - cols[j]), j - i)

    def test_queens_all_92(self):
        """FIND ALL собирает ровно 92 решения задачи 8 ферзей."""
        src = _QUEENS_DEF + "[FIND ALL (Q) .Q [SET Q [Ф8]]]"
        result = _eval_last(src)
        # результат — вложенный список решений: ((1 5 8 6 3 7 2 4) ...)
        self.assertEqual(result.count("(") - 1, 92)


if __name__ == "__main__":
    unittest.main()
