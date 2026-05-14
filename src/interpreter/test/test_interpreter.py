import io
import sys
import textwrap
import unittest

from src.interpreter import PlannerInterpreter, PlannerRuntimeError
from src.lexer import Lexer
from src.parser import PlannerParser


def _run(source: str) -> str:
    groups = Lexer(source).tokenize()
    prog   = PlannerParser().parse(groups)
    buf    = io.StringIO()
    old    = sys.stdout
    sys.stdout = buf
    try:
        PlannerInterpreter().run(prog)
    finally:
        sys.stdout = old
    return buf.getvalue()


def _eval(source: str) -> str:
    lines = _run(source).strip().splitlines()
    return lines[-1] if lines else ""


class TestArithmetic(unittest.TestCase):

    def test_addition(self):
        self.assertEqual(_eval("[+ 2 3]"), "5")

    def test_subtraction(self):
        self.assertEqual(_eval("[- 10 3]"), "7")

    def test_multiplication(self):
        self.assertEqual(_eval("[× 3 7]"), "21")

    def test_nested_arithmetic(self):
        self.assertEqual(_eval("[- [+ 3 6] [- 4 2]]"), "7")

    def test_multi_arg_add(self):
        self.assertEqual(_eval("[+ 4 -3 0]"), "1")

    def test_integer_identity(self):
        self.assertEqual(_eval("42"), "42")

    def test_negative_int(self):
        self.assertEqual(_eval("-9"), "-9")


class TestListOperations(unittest.TestCase):

    def test_length(self):
        self.assertEqual(_eval("[LENGTH (A B C D)]"), "4")

    def test_elem(self):
        self.assertEqual(_eval("[ELEM 2 (A B C D)]"), "B")

    def test_rest(self):
        self.assertEqual(_eval("[REST 1 (A B C D)]"), "(B C D)")

    def test_head(self):
        self.assertEqual(_eval("[HEAD 2 (A B C D)]"), "(A B)")

    def test_empty_list(self):
        self.assertEqual(_eval("()"), "()")

    def test_nested_list(self):
        result = _eval("((1 2) (3 4))")
        self.assertIn("1", result)
        self.assertIn("4", result)


class TestPredicates(unittest.TestCase):

    def test_num_true(self):
        self.assertEqual(_eval("[NUM 42]"), "T")

    def test_atom_true(self):
        self.assertEqual(_eval("[ATOM ABC]"), "T")

    def test_list_true(self):
        self.assertEqual(_eval("[LIST (1 2 3)]"), "T")

    def test_empty_true(self):
        self.assertEqual(_eval("[EMPTY ()]"), "T")

    def test_empty_false(self):
        self.assertEqual(_eval("[EMPTY (A B)]"), "()")

    def test_num_false_on_atom(self):
        self.assertEqual(_eval("[NUM ABC]"), "()")


class TestVariables(unittest.TestCase):

    def test_cset_and_read(self):
        output = _run("[CSET PI 3.14159]\n:PI")
        lines = output.strip().splitlines()
        self.assertIn("3.14159", lines[-1])

    def test_prog_set(self):
        self.assertEqual(_eval("[PROG (X) [SET X 10] [+ .X 5]]"), "15")

    def test_prog_nested(self):
        result = _eval("[PROG (A B) [SET A 3] [SET B 4] [+ .A .B]]")
        self.assertEqual(result, "7")


class TestConditional(unittest.TestCase):

    def test_true_clause(self):
        result = _eval("[COND (() первая-ложна) (T нашли-истину)]")
        self.assertEqual(result, "нашли-истину")

    def test_first_true(self):
        result = _eval("[COND (T первый-истинный) (T второй)]")
        self.assertEqual(result, "первый-истинный")

    def test_all_false(self):
        result = _eval("[COND (() нет1) (() нет2)]")
        self.assertEqual(result, "()")


class TestFunctions(unittest.TestCase):

    def test_square(self):
        self.assertEqual(_eval("[DEFINE SQUARE (LAMBDA (N) [× .N .N])]\n[SQUARE 7]"), "49")

    def test_factorial(self):
        src = textwrap.dedent("""
            [DEFINE FACT (LAMBDA (N)
            [COND ([LE .N 1] 1)
                    (T [× .N [FACT [- .N 1]]])])]
            [FACT 5]
            """
        )
        self.assertEqual(_eval(src), "120")

    def test_recursive_member(self):
        src = textwrap.dedent("""
            [DEFINE MEMBER (LAMBDA (A L)
                [COND ([EQ .L ()] ())
                    ([EQ .A [ELEM 1 .L]] T)
                    (T [MEMBER .A [REST 1 .L]])])]
            [MEMBER 2 (1 2 3)]
            """
        )
        self.assertEqual(_eval(src), "T")


class TestLoops(unittest.TestCase):

    def test_for_sum(self):
        src = "[PROG (S) [SET S 0] [FOR I 5 [SET S [+ .S .I]]] .S]"
        self.assertEqual(_eval(src), "15")


class TestSegmented(unittest.TestCase):

    def test_slist(self):
        result = _eval("<REST 1 (A B C D)>")
        self.assertEqual(result, "(B C D)")


class TestRuntimeErrors(unittest.TestCase):

    def test_unbound_variable(self):
        with self.assertRaises(PlannerRuntimeError):
            _run("[+ .UNBOUND 1]")

    def test_wrong_arg_count(self):
        with self.assertRaises(PlannerRuntimeError):
            _run("[DEFINE F (LAMBDA (X) .X)]\n[F 1 2 3]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
