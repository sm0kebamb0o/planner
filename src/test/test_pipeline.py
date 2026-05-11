"""
End-to-end pipeline tests: Lexer -> Parser -> Interpreter.

Tests cover the full pipeline from raw source text to evaluated output,
using example programs from the examples/ directory as well as inline sources.
"""

import io
import os
import sys
import unittest

from src.interpreter import PlannerInterpreter
from src.interpreter.models.signals import PlannerFailure
from src.lexer import Lexer
from src.parser import PlannerParser

_EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(source: str) -> str:
    """Run a Planner source string through the full pipeline; return stdout."""
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
    """Run source and return the last non-empty output line (the final value)."""
    lines = [l for l in _run(source).strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def _read_example(rel_path: str) -> str:
    with open(os.path.join(_EXAMPLES, rel_path), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Smoke tests: each parseable example file runs without raising an exception
# ---------------------------------------------------------------------------

class TestPipelineSmoke(unittest.TestCase):
    """Each example file must run without any uncaught exception."""

    def _smoke(self, rel_path: str) -> None:
        try:
            _run(_read_example(rel_path))
        except Exception as exc:
            self.fail(f"{rel_path} raised {type(exc).__name__}: {exc}")

    def test_smoke_01_basics(self):
        self._smoke("01_basics.pl")

    def test_smoke_02_arithmetic(self):
        self._smoke("02_arithmetic.pl")

    def test_smoke_04_recursion(self):
        self._smoke("04_recursion.pl")


# ---------------------------------------------------------------------------
# 01_basics.pl: atoms, numbers, lists, type predicates
# ---------------------------------------------------------------------------

class TestPipelineBasics(unittest.TestCase):
    """Atoms evaluate to themselves; predicates return T or ()."""

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


# ---------------------------------------------------------------------------
# 02_arithmetic.pl: arithmetic operations
# ---------------------------------------------------------------------------

class TestPipelineArithmetic(unittest.TestCase):
    """Arithmetic operations produce correct results."""

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


# ---------------------------------------------------------------------------
# 04_recursion.pl: user-defined recursive functions
# ---------------------------------------------------------------------------

class TestPipelineRecursion(unittest.TestCase):
    """Recursive functions produce correct results."""

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


# ---------------------------------------------------------------------------
# List operations (inline)
# ---------------------------------------------------------------------------

class TestPipelineLists(unittest.TestCase):
    """Built-in list operations return correct results."""

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


# ---------------------------------------------------------------------------
# Backtracking: SUM (find subsets summing to N)
# ---------------------------------------------------------------------------

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
    """SUM: find subsets of a list that sum to N."""

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


# ---------------------------------------------------------------------------
# Backtracking: 8-queens
# ---------------------------------------------------------------------------

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
    """8-queens: find a non-attacking placement of 8 queens."""

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
