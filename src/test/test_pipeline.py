import io
import os
import sys
import unittest

from src.interpreter import PlannerInterpreter
from src.lexer import Lexer
from src.parser import PlannerParser


def _run(source: str) -> str:
    groups = Lexer(source).tokenize()
    prog = PlannerParser().parse(groups)
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        PlannerInterpreter().run(prog)
    finally:
        sys.stdout = old
    return buf.getvalue()


def _eval(source: str) -> str:
    lines = [l for l in _run(source).strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


class TestPipelineBasics(unittest.TestCase):

    def test_atom_evaluates_to_itself(self):
        self.assertIn("HELLO", _run("HELLO"))

    def test_integer_evaluates_to_itself(self):
        self.assertIn("42", _run("42"))

    def test_float_evaluates_to_itself(self):
        self.assertIn("3.14159", _run("3.14159"))

    def test_empty_list(self):
        self.assertEqual(_eval("()"), "()")

    def test_predicate_num_true(self):
        self.assertEqual(_eval("[NUM 42]"), "T")

    def test_predicate_num_false(self):
        self.assertEqual(_eval("[NUM HELLO]"), "()")

    def test_predicate_atom_true(self):
        self.assertEqual(_eval("[ATOM WORLD]"), "T")

    def test_predicate_atom_false_on_list(self):
        self.assertEqual(_eval("[ATOM (A B)]"), "()")

    def test_predicate_list_true(self):
        self.assertEqual(_eval("[LIST (1 2 3)]"), "T")

    def test_predicate_list_false(self):
        self.assertEqual(_eval("[LIST 99]"), "()")

    def test_predicate_empty_true(self):
        self.assertEqual(_eval("[EMPTY ()]"), "T")

    def test_predicate_empty_false(self):
        self.assertEqual(_eval("[EMPTY (A B)]"), "()")

    def test_predicate_int_true(self):
        self.assertEqual(_eval("[INT 5]"), "T")

    def test_predicate_real_true(self):
        self.assertEqual(_eval("[REAL 3.14]"), "T")


class TestPipelineComments(unittest.TestCase):

    def test_comments_are_not_evaluated_or_printed(self):
        source = "# [FAIL]\n[+ 1# ] [FAIL]\n2]# [FAIL]"
        self.assertEqual(_run(source), _run("[+ 1 2]"))

    def test_comment_only_program(self):
        self.assertEqual(_run("# [FAIL]\n# пояснение"), "")

    def test_comments_in_backtracking_program(self):
        source = """
        [DATA (BOX A) (BOX B)] # исходные данные
        [PROG (X)
            [SEARCH (BOX *X)] # первый кандидат — A
            # [FAIL] здесь не выполняется
            [UNFALSE [NEQ .X A]] # возврат к поиску
            .X]# результат — B
        """
        self.assertEqual(_eval(source), "B")


class TestPipelineDatabase(unittest.TestCase):

    def test_assert_then_search(self):
        src = "[ASSERT (AT BOX R1)]\n[SEARCH (AT BOX R1)]"
        self.assertEqual(_eval(src), "(AT BOX R1)")

    def test_assert_evaluates_variables_in_fact(self):
        src = """
        [PROG ((ROOM R2))
            [ASSERT (AT BOX .ROOM)]
            [SEARCH (AT BOX R2)]]
        """
        self.assertEqual(_eval(src), "(AT BOX R2)")

    def test_data_then_collect_all_matches(self):
        src = """
        [DATA (BOX A) (ROOM R1) (BOX B) (BOX C)]
        [FIND ALL (X) .X [SEARCH (BOX *X)]]
        """
        self.assertEqual(_eval(src), "(C B A)")

    def test_duplicate_assert_does_not_add_another_match(self):
        src = """
        [DATA (BOX A)]
        [ASSERT (BOX A)]
        [FIND ALL (X) .X [SEARCH (BOX *X)]]
        """
        self.assertEqual(_eval(src), "(A)")

    def test_db_search_filters_properties_and_restores_rejected_bindings(self):
        src = """
        [DB (STUDENT PETROV) (COURSE 4 FACULTY VMK)
            (STUDENT IVANOV) (COURSE 5 FACULTY MECHMAT)]
        [PROG (X Y)
            [SEARCH (STUDENT *X)
                (TEST COURSE *Y FACULTY [NON VMK])]
            (.X .Y)]
        """
        self.assertEqual(_eval(src), "(IVANOV 5)")

    def test_assert_with_properties_then_search(self):
        src = """
        [ASSERT (BOX A) (WITH COLOUR BLUE SIZE 3)]
        [ASSERT (BOX B) (WITH COLOUR RED SIZE 7)]
        [PROG (X SIZE)
            [SEARCH (BOX *X) (TEST COLOUR RED SIZE [ET [GE 5] *SIZE])]
            (.X .SIZE)]
        """
        self.assertEqual(_eval(src), "(B 7)")

    def test_search_resumes_when_continuation_fails(self):
        src = """
        [DATA (BOX A) (BOX B)]
        [PROG (X)
            [SEARCH (BOX *X)]
            [UNFALSE [NEQ .X A]]
            .X]
        """
        self.assertEqual(_eval(src), "B")

    def test_search1_returns_only_first_match(self):
        src = """
        [DATA (BOX A) (BOX B)]
        [FIND ALL (X) .X [SEARCH1 (BOX *X)]]
        """
        self.assertEqual(_eval(src), "(A)")

    def test_search_reports_missing_fact(self):
        self.assertEqual(_eval("[DATA (BOX A)]\n[SEARCH (BOX B)]"),
                         "=НЕУСПЕХ= SEARCH")

    def test_search_decodes_stored_pattern(self):
        src = """
        [DATA (BOX A) (BOX B)]
        [PROG (P X)
            [SET P [QUOTE (BOX *X)]]
            [SEARCH .P]
            .X]
        """
        self.assertEqual(_eval(src), "A")

    def test_search_matches_nested_fact_with_variable_predicate(self):
        src = """
        [DATA (LOCATION (BOX A) R1) (OWNER (BOX A) IVANOV)]
        [FIND ALL (P X) (.P .X) [SEARCH (*P (BOX A) *X)]]
        """
        self.assertEqual(_eval(src), "((OWNER IVANOV) (LOCATION R1))")

    def test_assert_is_rolled_back_before_subsequent_search(self):
        src = "[GATE [ASSERT (BOX A)] [FAIL]]\n[SEARCH (BOX A)]"
        self.assertEqual(_eval(src), "=НЕУСПЕХ= SEARCH")

    def test_passert_survives_failure_and_is_searchable(self):
        src = "[GATE [PASSERT (BOX A)] [FAIL]]\n[SEARCH (BOX A)]"
        self.assertEqual(_eval(src), "(BOX A)")

    def test_search_excludes_facts_added_during_enumeration(self):
        src = """
        [DATA (BOX A) (BOX B)]
        [FIND ALL (X) .X
            [SEARCH (BOX *X)]
            [PASSERT (BOX C)]]
        """
        self.assertEqual(_eval(src), "(B A)")


class TestPipelineArithmetic(unittest.TestCase):

    def test_addition_multi(self):
        self.assertEqual(_eval("[+ 1 2 3 4 5]"), "15")

    def test_subtraction(self):
        self.assertEqual(_eval("[- 100 37]"), "63")

    def test_multiplication_multi(self):
        self.assertEqual(_eval("[× 2 3 4]"), "24")

    def test_integer_division(self):
        self.assertEqual(_eval("[DIV 7 2]"), "3")

    def test_modulo(self):
        self.assertEqual(_eval("[MOD 17 5]"), "2")

    def test_power(self):
        self.assertEqual(_eval("[↑ 2 10]"), "1024")

    def test_abs(self):
        self.assertEqual(_eval("[ABS -42]"), "42")

    def test_comparison_lt_true(self):
        self.assertEqual(_eval("[LT 3 5]"), "T")

    def test_comparison_lt_false(self):
        self.assertEqual(_eval("[LT 5 3]"), "()")

    def test_comparison_ge_equal(self):
        self.assertEqual(_eval("[GE 5 5]"), "T")

    def test_nested_arithmetic(self):
        self.assertEqual(_eval("[+ [× 3 4] [- 10 4]]"), "18")


class TestPipelineRecursion(unittest.TestCase):

    _FACT = "[DEFINE FACT (LAMBDA (N) [COND ([LE .N 1] 1) (T [× .N [FACT [- .N 1]]])])]\n"
    _FIB = "[DEFINE FIB (LAMBDA (N) [COND ([LE .N 0] 0) ([EQ .N 1] 1) (T [+ [FIB [- .N 1]] [FIB [- .N 2]]])])]\n"

    def test_factorial_0(self):
        self.assertEqual(_eval(self._FACT + "[FACT 0]"), "1")

    def test_factorial_5(self):
        self.assertEqual(_eval(self._FACT + "[FACT 5]"), "120")

    def test_factorial_10(self):
        self.assertEqual(_eval(self._FACT + "[FACT 10]"), "3628800")

    def test_fibonacci_0(self):
        self.assertEqual(_eval(self._FIB + "[FIB 0]"), "0")

    def test_fibonacci_10(self):
        self.assertEqual(_eval(self._FIB + "[FIB 10]"), "55")

    def test_gcd(self):
        src = "[DEFINE GCD (LAMBDA (A B) [COND ([EQ .B 0] .A) (T [GCD .B [MOD .A .B]])])]\n[GCD 48 18]"
        self.assertEqual(_eval(src), "6")

    def test_recursive_member_found(self):
        src = (
            "[DEFINE MEMBER (LAMBDA (A L)"
            " [COND ([EQ .L ()] ())"
            "       ([EQ .A [ELEM 1 .L]] T)"
            "       (T [MEMBER .A [REST 1 .L]])])]\n"
            "[MEMBER 3 (1 2 3 4)]"
        )
        self.assertEqual(_eval(src), "T")

    def test_recursive_member_not_found(self):
        src = (
            "[DEFINE MEMBER (LAMBDA (A L)"
            " [COND ([EQ .L ()] ())"
            "       ([EQ .A [ELEM 1 .L]] T)"
            "       (T [MEMBER .A [REST 1 .L]])])]\n"
            "[MEMBER 9 (1 2 3 4)]"
        )
        self.assertEqual(_eval(src), "()")


class TestPipelineLists(unittest.TestCase):

    def test_length(self):
        self.assertEqual(_eval("[LENGTH (A B C D E)]"), "5")

    def test_elem(self):
        self.assertEqual(_eval("[ELEM 2 (A B C D E)]"), "B")

    def test_rest(self):
        self.assertEqual(_eval("[REST 2 (A B C D E)]"), "(C D E)")

    def test_head(self):
        self.assertEqual(_eval("[HEAD 3 (A B C D E)]"), "(A B C)")

    def test_memb_found(self):
        self.assertEqual(_eval("[MEMB C (A B C D)]"), "3")

    def test_sum_list_recursive(self):
        src = (
            "[DEFINE SUM-LIST (LAMBDA (L)"
            " [COND ([EMPTY .L] 0)"
            "       (T [+ [ELEM 1 .L] [SUM-LIST [REST 1 .L]]])])]\n"
            "[SUM-LIST (10 20 30 40 50)]"
        )
        self.assertEqual(_eval(src), "150")

_SUM_DEF = """\
[DEFINE SUM (LAMBDA (L N)
  [PROG (K (M ()) (S 0))
    A [SET K  [AMONG .L]]
      [SET M  (!.M .K)]
      [SET S  [+ .S .K]]
      [COND ([EQ .S .N] .M)
            ([LT .S .N] [GO A])
            (T [FAIL])]])]
"""


class TestPipelineBacktrackingSum(unittest.TestCase):

    def test_first_solution(self):
        result = _eval(_SUM_DEF + "[SUM (6 3 2 1) 5]")
        self.assertEqual(result, "(3 2)")

    def test_length_4_solution(self):
        src = _SUM_DEF + (
            "[PROG (X) [SET X [SUM (6 3 2 1) 5]]\n"
            "          [COND ([NEQ [LENGTH .X] 4] [FAIL])]\n"
            "          .X]"
        )
        self.assertEqual(_eval(src), "(2 1 1 1)")

    def test_no_solution_produces_failure(self):
        output = _run(_SUM_DEF + "[SUM (4 2) 7]")
        self.assertIn("НЕУСПЕХ", output)

    def test_collect_all_solutions(self):
        src = _SUM_DEF + (
            "[DO [ALT () [EXIT T DO]]\n"
            "    [PRINT [SUM (3 2 1) 3]]\n"
            "    [FAIL]]"
        )
        output = _run(src)
        self.assertIn("(3)", output)
        self.assertIn("(2 1)", output)


_QUEENS_DEF = """\
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


class TestPipelineBacktrackingQueens(unittest.TestCase):

    def test_first_solution_value(self):
        result = _eval(_QUEENS_DEF + "[Ф8]")
        self.assertEqual(result, "(1 5 8 6 3 7 2 4)")

    def test_solution_has_8_queens(self):
        result = _eval(_QUEENS_DEF + "[Ф8]")
        cols = [int(x) for x in result.strip("()").split()]
        self.assertEqual(len(cols), 8)

    def test_solution_uses_each_column_once(self):
        result = _eval(_QUEENS_DEF + "[Ф8]")
        cols = [int(x) for x in result.strip("()").split()]
        self.assertEqual(sorted(cols), list(range(1, 9)))

    def test_solution_no_diagonal_attacks(self):
        result = _eval(_QUEENS_DEF + "[Ф8]")
        cols = [int(x) for x in result.strip("()").split()]
        for i in range(8):
            for j in range(i + 1, 8):
                self.assertNotEqual(abs(cols[i] - cols[j]), j - i)


if __name__ == "__main__":
    unittest.main(verbosity=2)
