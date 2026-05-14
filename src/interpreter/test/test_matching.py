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
        result = _eval_last("[PROG (X) [IS *X HELLO] .X]")
        self.assertEqual(result, "HELLO")

    def test_dot_var_bind(self):
        result = _eval_last("[PROG (X) [IS .X WORLD] .X]")
        self.assertEqual(result, "WORLD")

    def test_dot_var_check_equal(self):
        result = _eval_last("[PROG (X) [SET X A] [IS .X A]]")
        self.assertEqual(result, "T")

    def test_dot_var_check_unequal(self):
        result = _eval_last("[PROG (X) [SET X A] [IS .X B]]")
        self.assertEqual(result, "()")

    def test_dot_var_same_twice(self):
        result = _eval_last("[PROG (X) [IS (.X .X) (A A)]]")
        self.assertEqual(result, "T")

    def test_dot_var_different(self):
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

class TestISSegmented(unittest.TestCase):

    def test_segmented_star_binds_list(self):
        result = _eval_last("[PROG (X) [IS (!*X) (A B C)] .X]")
        self.assertEqual(result, "(A B C)")

    def test_segmented_split(self):
        result = _eval_last("[PROG (X Y) [IS (!*X *Y) (1 2 3)] .X]")
        self.assertEqual(result, "(1 2)")

    def test_segmented_middle(self):
        result = _eval_last("[PROG (X) [IS (A !*X B) (A 1 2 B)] .X]")
        self.assertEqual(result, "(1 2)")

    def test_segmented_empty(self):
        result = _eval_last("[PROG (X) [IS (!*X A) (A)] .X]")
        self.assertEqual(result, "()")

    def test_segmented_plus_pattern(self):
        result = _eval_last("[PROG (X Y) [IS (!*X + !*Y) (1 2 + 3 4)] [LENGTH .X]]")
        self.assertEqual(result, "2")


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
        self.assertEqual(_eval_last("[IS [NON [NUM]] ABC]"), "T")

    def test_matcher_non_fail(self):
        self.assertEqual(_eval_last("[IS [NON [NUM]] 42]"), "()")

    def test_matcher_gt(self):
        self.assertEqual(_eval_last("[IS [GT 3] 5]"), "T")

    def test_matcher_gt_fail(self):
        self.assertEqual(_eval_last("[IS [GT 3] 2]"), "()")

    def test_matcher_et(self):
        self.assertEqual(_eval_last("[IS [ET [NUM] [GT 0]] 5]"), "T")

    def test_matcher_et_fail(self):
        self.assertEqual(_eval_last("[IS [ET [NUM] [GT 0]] -1]"), "()")

    def test_matcher_aut(self):
        self.assertEqual(_eval_last("[IS [AUT [NUM] [ID]] ABC]"), "T")
        self.assertEqual(_eval_last("[IS [AUT [NUM] [ID]] 42]"), "T")

    def test_matcher_one_of(self):
        self.assertEqual(_eval_last("[IS [ONE-OF (A B C)] B]"), "T")

    def test_matcher_one_of_fail(self):
        self.assertEqual(_eval_last("[IS [ONE-OF (A B C)] D]"), "()")

    def test_star_matcher(self):
        self.assertEqual(_eval_last("[IS [STAR [NUM]] (1 2 3)]"), "T")

    def test_star_matcher_fail(self):
        self.assertEqual(_eval_last("[IS [STAR [NUM]] (1 A 3)]"), "()")


class TestVARMatchers(unittest.TestCase):

    def test_var_dot(self):
        self.assertEqual(_eval_last("[IS [VAR.] [QUOTE .X]]"), "T")

    def test_var_dot_no_match(self):
        self.assertEqual(_eval_last("[IS [VAR.] ABC]"), "()")

    def test_var_star(self):
        self.assertEqual(_eval_last("[IS [VAR*] [QUOTE *Y]]"), "T")

    def test_var_star_no_match(self):
        self.assertEqual(_eval_last("[IS [VAR*] [QUOTE .Y]]"), "()")

    def test_var_colon(self):
        self.assertEqual(_eval_last("[IS [VAR:] [QUOTE :C]]"), "T")

    def test_var_seg_dot(self):
        self.assertEqual(_eval_last("[IS [VAR!.] [QUOTE !.X]]"), "T")

    def test_var_seg_star(self):
        self.assertEqual(_eval_last("[IS [VAR!*] [QUOTE !*Y]]"), "T")

    def test_var_seg_colon(self):
        self.assertEqual(_eval_last("[IS [VAR!:] [QUOTE !:C]]"), "T")

    def test_varp_dot(self):
        self.assertEqual(_eval_last("[IS [VARP] [QUOTE .X]]"), "T")

    def test_varp_star(self):
        self.assertEqual(_eval_last("[IS [VARP] [QUOTE *Y]]"), "T")

    def test_varp_seg_no_match(self):
        self.assertEqual(_eval_last("[IS [VARP] [QUOTE !*X]]"), "()")

    def test_vars_seg_star(self):
        self.assertEqual(_eval_last("[IS [VARS] [QUOTE !*Y]]"), "T")

    def test_vars_simple_no_match(self):
        self.assertEqual(_eval_last("[IS [VARS] [QUOTE .X]]"), "()")

    def test_var_any_simple(self):
        self.assertEqual(_eval_last("[IS [VAR] [QUOTE .X]]"), "T")

    def test_var_any_seg(self):
        self.assertEqual(_eval_last("[IS [VAR] [QUOTE !:C]]"), "T")

    def test_var_no_match_atom(self):
        self.assertEqual(_eval_last("[IS [VAR] ABC]"), "()")


class TestLISTLengthPattern(unittest.TestCase):

    def test_list_length_star_bind(self):
        result = _eval_last("[PROG (X) [IS [LIST *X] (A B C)] .X]")
        self.assertEqual(result, "3")

    def test_list_length_gt_match(self):
        self.assertEqual(_eval_last("[IS [LIST [GT 1]] (A B)]"), "T")

    def test_list_length_gt_no_match(self):
        self.assertEqual(_eval_last("[IS [LIST [GT 1]] (A)]"), "()")

    def test_list_length_exact(self):
        self.assertEqual(_eval_last("[IS [LIST 2] (A B)]"), "T")
        self.assertEqual(_eval_last("[IS [LIST 2] (A)]"), "()")

    def test_listr_length_bind(self):
        result = _eval_last("[PROG (X) [IS [LISTR *X] [QUOTE [A B]]] .X]")
        self.assertEqual(result, "2")

    def test_list_length_dot_check(self):
        result = _eval_last("[PROG (N) [SET N 3] [IS [LIST .N] (A B C)]]")
        self.assertEqual(result, "T")

    def test_list_length_dot_no_match(self):
        result = _eval_last("[PROG (N) [SET N 4] [IS [LIST .N] (A B C)]]")
        self.assertEqual(result, "()")


class TestSegmentedMatchers(unittest.TestCase):

    def test_segmented_star_matcher(self):
        result = _eval_last("[IS (A <STAR [NUM]> B) (A 1 2 3 B)]")
        self.assertEqual(result, "T")

    def test_segmented_star_matcher_fail(self):
        result = _eval_last("[IS (A <STAR [NUM]> B) (A 1 X 3 B)]")
        self.assertEqual(result, "()")

    def test_segmented_star_empty(self):
        result = _eval_last("[IS (A <STAR [NUM]> B) (A B)]")
        self.assertEqual(result, "T")

    def test_segmented_listr_wildcard(self):
        result = _eval_last("[IS (A <LISTR> B) (A 1 2 B)]")
        self.assertEqual(result, "T")

    def test_segmented_listr_length_bind(self):
        result = _eval_last("[PROG (N) [IS (A <LISTR *N> B) (A 1 2 B)] .N]")
        self.assertEqual(result, "2")


class TestEmptyPListWildcard(unittest.TestCase):

    def test_matches_atom(self):
        self.assertEqual(_eval_last("[IS [] HELLO]"), "T")

    def test_matches_number(self):
        self.assertEqual(_eval_last("[IS [] 42]"), "T")

    def test_matches_list(self):
        self.assertEqual(_eval_last("[IS [] (A B)]"), "T")

    def test_in_list_pattern(self):
        self.assertEqual(_eval_last("[IS (A [] B) (A X B)]"), "T")
        self.assertEqual(_eval_last("[IS (A [] B) (A 99 B)]"), "T")

    def test_two_wildcards(self):
        self.assertEqual(_eval_last("[IS ([] []) (X Y)]"), "T")

    def test_wrong_length_fails(self):
        self.assertEqual(_eval_last("[IS (A [] B) (A B)]"), "()")


class TestEmptySegmentedWildcard(unittest.TestCase):

    def test_empty_wildcard_matches_any_segment(self):
        self.assertEqual(_eval_last("[IS (A <> B) (A 1 2 B)]"), "T")

    def test_empty_wildcard_empty_segment(self):
        self.assertEqual(_eval_last("[IS (A <> B) (A B)]"), "T")

    def test_empty_wildcard_standalone(self):
        self.assertEqual(_eval_last("[IS <> HELLO]"), "T")
        self.assertEqual(_eval_last("[IS <> 42]"), "T")
        self.assertEqual(_eval_last("[IS <> (A B)]"), "T")

    def test_empty_wildcard_multiple(self):
        self.assertEqual(_eval_last("[IS (<> A <>) (X A Y Z)]"), "T")
        self.assertEqual(_eval_last("[IS (<> A <>) (A)]"), "T")

    def test_kappa_contains_original(self):
        src = textwrap.dedent("""
            [DEFINE CONTAINS (KAPPA (*P) (<> [PAT .P] <>))]
            [IS [CONTAINS B] (A B C)]
            """
        )
        self.assertEqual(_eval_last(src), "T")

    def test_kappa_contains_fail(self):
        src = textwrap.dedent("""
            [DEFINE CONTAINS (KAPPA (*P) (<> [PAT .P] <>))]
            [IS [CONTAINS D] (A B C)]
            """
        )
        self.assertEqual(_eval_last(src), "()")

    def test_kappa_contains_matcher_arg(self):
        src = textwrap.dedent("""
            [DEFINE CONTAINS (KAPPA (*P) (<> [PAT .P] <>))]
                        [IS [CONTAINS [ATOM]] (1 2 X)]
            """
        )
        self.assertEqual(_eval_last(src), "T")


class TestKAPPA(unittest.TestCase):

    def test_kappa_no_args_success(self):
        src = textwrap.dedent("""
            [DEFINE NATOM (KAPPA () [NON [ATOM]])]
            [IS [NATOM] (A B C)]
            """
        )
        self.assertEqual(_eval_last(src), "T")

    def test_kappa_no_args_fail(self):
        src = textwrap.dedent("""
            [DEFINE NATOM (KAPPA () [NON [ATOM]])]
            [IS [NATOM] ABC]
            """
        )
        self.assertEqual(_eval_last(src), "()")

    def test_kappa_simple(self):
        src = textwrap.dedent("""
            [DEFINE GT0 (KAPPA () [GT 0])]
            [IS [GT0] 5]
            """
        )
        self.assertEqual(_eval_last(src), "T")

    def test_kappa_simple_fail(self):
        src = textwrap.dedent("""
            [DEFINE GT0 (KAPPA () [GT 0])]
            [IS [GT0] -3]
            """
        )
        self.assertEqual(_eval_last(src), "()")

    def test_kappa_with_params(self):
        src = textwrap.dedent("""
            [DEFINE LG (KAPPA (MIN MAX) [LISTR [ET [GE .MIN] [LE .MAX]]])]
            [IS [LG 2 4] (A B C)]
            """
        )
        self.assertEqual(_eval_last(src), "T")

    def test_kappa_with_params_fail(self):
        src = textwrap.dedent("""
            [DEFINE LG (KAPPA (MIN MAX) [LISTR [ET [GE .MIN] [LE .MAX]]])]
            [IS [LG 2 4] (A)]
            """
        )
        self.assertEqual(_eval_last(src), "()")

    def test_kappa_body_binds_outer_var(self):
        src = textwrap.dedent("""
            [DEFINE CAPTURE (KAPPA () *VAL)]
            [PROG (VAL)
                [IS [CAPTURE] HELLO]
                .VAL]
            """
        )
        self.assertEqual(_eval_last(src), "HELLO")

    def test_kappa_et_capture(self):
        src = textwrap.dedent("""
            [DEFINE NUM-CAPTURE (KAPPA () [ET [NUM] *N])]
            [PROG (N)
            [IS [NUM-CAPTURE] 42]
            .N]
            """
        )
        self.assertEqual(_eval_last(src), "42")


if __name__ == "__main__":
    unittest.main()
