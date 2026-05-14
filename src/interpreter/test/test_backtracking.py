import io
import sys
import textwrap
import unittest

from src.interpreter import PlannerInterpreter
from src.lexer import Lexer
from src.parser import PlannerParser


def _run_source(source: str, interp=None):
    groups = Lexer(source).tokenize()
    prog   = PlannerParser().parse(groups)
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
    values = lines[1::2]
    return lines, values


def _eval_last(source: str, interp=None) -> str:
    lines, values = _run_source(source, interp)
    return values[-1] if values else ""


class TestFailMess(unittest.TestCase):

    def test_fail_at_toplevel(self):
        lines, _ = _run_source("[FAIL]")
        self.assertTrue(any("НЕУСПЕХ" in l for l in lines))

    def test_fail_with_message(self):
        lines, _ = _run_source("[FAIL OOPS]")
        self.assertTrue(any("OOPS" in l for l in lines))

    def test_mess(self):
        result = _eval_last("[PROG (X) [GATE [FAIL HELLO]] [MESS]]")
        self.assertEqual(result, "HELLO")


class TestGate(unittest.TestCase):

    def test_gate_success(self):
        self.assertEqual(_eval_last("[GATE [+ 1 2]]"), "3")

    def test_gate_fail_returns_nil(self):
        self.assertEqual(_eval_last("[GATE [FAIL]]"), "()")

    def test_gate_among_fail(self):
        result = _eval_last("[GATE [AMONG (1 2 3)] [FAIL]]")
        self.assertEqual(result, "()")


class TestAMONG(unittest.TestCase):

    def test_among_first_value(self):
        result = _eval_last("[PROG (X) [SET X [AMONG (10 20 30)]] .X]")
        self.assertEqual(result, "10")

    def test_among_empty_fails(self):
        lines, _ = _run_source("[AMONG ()]")
        output = " ".join(lines)
        self.assertTrue("НЕУСПЕХ" in output or "AMONG" in output)

    def test_among_collect_all(self):
        result = _eval_last("[FIND ALL (X) .X [SET X [AMONG (1 2 3)]]]")
        self.assertEqual(result, "(3 2 1)")

    def test_alt_first_success(self):
        result = _eval_last("[PROG (X) [SET X [ALT 10 20]] .X]")
        self.assertEqual(result, "10")

    def test_alt_skip_fail(self):
        result = _eval_last("[PROG (X) [SET X [ALT [FAIL] 99]] .X]")
        self.assertEqual(result, "99")


class TestIF(unittest.TestCase):

    def test_if_first_match(self):
        result = _eval_last("[IF ([EQ 1 1] OK)]")
        self.assertEqual(result, "OK")

    def test_if_second_clause(self):
        result = _eval_last("[IF ([FAIL] A) (() B)]")
        self.assertEqual(result, "B")

    def test_if_all_fail(self):
        result = _eval_last("[IF ([FAIL] A) ([FAIL] B)]")
        self.assertEqual(result, "()")

    def test_if_no_body(self):
        result = _eval_last("[IF (T)]")
        self.assertEqual(result, "T")


class TestFIND(unittest.TestCase):

    def test_find_all_among(self):
        result = _eval_last("[FIND ALL (X) .X [SET X [AMONG (A B C)]]]")
        self.assertEqual(result, "(C B A)")

    def test_find_exact_count(self):
        result = _eval_last("[FIND 2 (X) .X [SET X [AMONG (1 2 3 4)]]]")
        self.assertEqual(result, "(2 1)")

    def test_find_with_filter(self):
        result = _eval_last(
            "[FIND ALL (X) .X "
            " [SET X [AMONG (1 -2 3 -5)]]"
            " [COND ([LT .X 0] [FAIL])]]"
        )
        self.assertEqual(result, "(3 1)")

    def test_find_zero_returns_nil(self):
        result = _eval_last("[FIND 0 (X) .X [SET X [AMONG (1 2)]]]")
        self.assertEqual(result, "()")


class TestPermanent(unittest.TestCase):

    def test_pset_not_undone(self):
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


class TestTrailRollback(unittest.TestCase):

    def test_set_rolled_back(self):
        result = _eval_last(
            "[PROG (X) "
            " [SET X 0]"
            " [GATE [SET X [AMONG (1 2 3)]] [FAIL]]"
            " .X]"
        )
        self.assertEqual(result, "0")

    def test_add1_rolled_back(self):
        result = _eval_last(
            "[PROG (N) "
            " [SET N 0]"
            " [GATE [ADD1 N] [FAIL]]"
            " .N]"
        )
        self.assertEqual(result, "0")

    def test_is_binding_rolled_back(self):
        result = _eval_last(
            "[PROG (X) "
            " [GATE [IS *X HELLO] [FAIL]]"
            " [BOUND X]]"
        )
        self.assertEqual(result, "T")

class TestSUM(unittest.TestCase):

    def test_sum_basic(self):
        src = textwrap.dedent("""
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
        )
        result = _eval_last(src)
        groups = Lexer(result.strip("()").replace(" ", " ")).tokenize()
        self.assertNotIn("НЕУСПЕХ", result)
        self.assertTrue(result.startswith("("))

    def test_sum_no_solution(self):
        """SUM без решения → НЕУСПЕХ."""
        src = textwrap.dedent("""
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
        )
        lines, _ = _run_source(src)
        self.assertTrue(any("НЕУСПЕХ" in l for l in lines))

    def test_sum_first_solution(self):
        src = textwrap.dedent("""
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
        )
        self.assertEqual(_eval_last(src), "(3 2)")

    def test_sum_length4(self):
        src = textwrap.dedent("""
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
        )
        self.assertEqual(_eval_last(src), "(2 1 1 1)")

    def test_sum_all_solutions(self):
        src = textwrap.dedent("""
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
        )
        lines, values = _run_source(src)
        solutions = [v for v in values if v.startswith("(")]
        self.assertGreater(len(solutions), 1)
        for sol in solutions:
            nums = [int(x) for x in sol.strip("()").split()]
            self.assertEqual(sum(nums), 5)


_QUEENS_DEF = textwrap.dedent("""
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
)


class TestQueens(unittest.TestCase):

    def test_queens_first_solution(self):
        result = _eval_last(_QUEENS_DEF + "[Ф8]")
        self.assertEqual(result, "(1 5 8 6 3 7 2 4)")

    def test_queens_solution_is_valid(self):
        result = _eval_last(_QUEENS_DEF + "[Ф8]")
        cols = [int(x) for x in result.strip("()").split()]
        self.assertEqual(len(cols), 8)
        self.assertEqual(sorted(cols), list(range(1, 9)))
        for i in range(8):
            for j in range(i + 1, 8):
                self.assertNotEqual(abs(cols[i] - cols[j]), j - i)

    def test_queens_all_92(self):
        src = _QUEENS_DEF + "[FIND ALL (Q) .Q [SET Q [Ф8]]]"
        result = _eval_last(src)
        self.assertEqual(result.count("(") - 1, 92)


if __name__ == "__main__":
    unittest.main()
