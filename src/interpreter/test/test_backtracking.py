import io
import sys
import textwrap
import unittest

from src.interpreter import PlannerInterpreter, PlannerRuntimeError, PlannerFailure
from src.interpreter.functions import codec
from src.interpreter.control_flow import EvalStream
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


class TestSpecialFormFailures(unittest.TestCase):

    def test_ordinary_failure_exhausts_special_form_and_preserves_message(self):
        for source in ("[AMONG [FAIL MESSAGE]]", "[COND ([FAIL MESSAGE] 1)]"):
            with self.subTest(source=source):
                interp = PlannerInterpreter()
                node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
                self.assertEqual(list(interp.eval_form_bt(node)), [])
                self.assertEqual(interp._last_failure, "MESSAGE")
                self.assertEqual(len(interp.env._frames), 0)

    def test_named_failure_is_not_consumed_by_dispatcher(self):
        source = "[AMONG [FAIL MESSAGE POINT]]"
        interp = PlannerInterpreter()
        node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
        with self.assertRaises(PlannerFailure) as failure:
            list(interp.eval_form_bt(node))
        self.assertEqual(failure.exception.target, "POINT")
        self.assertEqual(failure.exception.message, "MESSAGE")
        self.assertEqual(_eval_last(f"[FP POINT {source} 9]"), "9")

    def test_control_exhaustion_does_not_create_fallback_results(self):
        for body in (
            "[GATE [RETURN [AMONG (1 2)]]]",
            "[IF ([RETURN [AMONG (1 2)]] 99) (T 77)]",
            "[FIND ALL () 99 [RETURN [AMONG (1 2)]]]",
        ):
            with self.subTest(body=body):
                interp = PlannerInterpreter()
                node = PlannerParser().parse(Lexer(f"[PROG () {body}]").tokenize()).forms[0]
                self.assertEqual(list(interp.eval_form_bt(node)), [1, 2])
                self.assertEqual(interp.env._frames, [])
                self.assertEqual(len(interp.env._frames), 0)

    def test_runtime_errors_are_not_converted_to_failure(self):
        with self.assertRaises(PlannerRuntimeError):
            _eval_last("[GATE [UNKNOWN]]")

    def test_loop_and_find_remove_local_scope_before_yielding(self):
        for source, expected in (
            ("[PROG ((X 100)) [+ [LOOP X (5) .X] .X]]", "105"),
            ("[PROG ((X 100)) [+ [LENGTH [FIND ALL ((X 5)) .X]] .X]]", "101"),
        ):
            with self.subTest(source=source):
                self.assertEqual(_eval_last(source), expected)


class TestGeneratorOwnership(unittest.TestCase):

    def test_run_closes_nested_streams_without_enumerating_extra_choices(self):
        for source, expected, visited in (
            ("[FIND 1 (X) .X [SET X [OBSERVE]]]", "(1)", [1]),
            ("[FIND ALL (X) .X [SET X [OBSERVE]]]", "(3 2 1)", [1, 2, 3]),
            ("[PROG () [DO [OBSERVE] [GO OUT]] [UNKNOWN] OUT 9]", "9", [1]),
            ("[PROG () [FIND ALL (X) .X [SET X [OBSERVE]] [RETURN .X]] 99]", "1", [1]),
            ("[DO [OBSERVE] [UNKNOWN]]", None, [1]),
        ):
            with self.subTest(source=source):
                events = []

                def observe(args: list) -> EvalStream:
                    try:
                        for value in (1, 2, 3):
                            events.append(value)
                            yield value
                    finally:
                        events.append("CLOSED")

                interp = PlannerInterpreter()
                interp._bt_fsubrs["OBSERVE"] = observe
                if expected is None:
                    with self.assertRaises(PlannerRuntimeError):
                        _eval_last(source, interp)
                else:
                    self.assertEqual(_eval_last(source, interp), expected)
                self.assertEqual(events, visited + ["CLOSED"])
                self.assertEqual(interp.env._frames, [])


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


class TestComputedCallHead(unittest.TestCase):

    def test_prog_backtracks_to_next_function_name(self):
        source = """
        [PROG (X)
            [SET X [[AMONG (+ -)] 5 2]]
            [UNFALSE [EQ .X 3]]
            .X]
        """
        self.assertEqual(_eval_last(source), "3")

    def test_head_and_argument_alternatives_are_exhausted_in_order(self):
        for source, expected in (
            ("[[AMONG (+ -)] [AMONG (5 6)] 2]", [7, 8, 3, 4]),
            ("<[AMONG (+ -)] [AMONG (5 6)] 2>", [[7], [8], [3], [4]]),
        ):
            with self.subTest(source=source):
                interp = PlannerInterpreter()
                node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
                values = list(interp.eval_form_bt(node))
                if source.startswith("<"):
                    values = [value.elements for value in values]
                self.assertEqual(values, expected)
                self.assertEqual(len(interp.env._frames), 0)

    def test_exhaustion_restores_head_and_call_bindings(self):
        interp = PlannerInterpreter()
        interp.env.push_frame(["F", "X"], {"F": "ORIGINAL", "X": 0})
        source = "[SET X [[ALT [SET F +] [SET F -]] 5 2]]"
        node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
        gen = interp.eval_form_bt(node)
        self.assertEqual(next(gen), 7)
        self.assertEqual(interp.env.get_local("F"), "+")
        self.assertEqual(interp.env.get_local("X"), 7)
        self.assertEqual(next(gen), 3)
        self.assertEqual(interp.env.get_local("F"), "-")
        self.assertEqual(interp.env.get_local("X"), 3)
        with self.assertRaises(StopIteration):
            next(gen)
        self.assertEqual(interp.env.get_local("F"), "ORIGINAL")
        self.assertEqual(interp.env.get_local("X"), 0)
        self.assertIsNone(gen.gi_frame)

    def test_close_accepts_first_branch_and_cleans_forks(self):
        interp = PlannerInterpreter()
        interp.env.push_frame(["F", "X"], {"F": "ORIGINAL", "X": 0})
        source = "[SET X [[ALT [SET F +] [SET F -]] 5 2]]"
        node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
        gen = interp.eval_form_bt(node)
        self.assertEqual(next(gen), 7)
        gen.close()
        self.assertEqual(interp.env.get_local("F"), "+")
        self.assertEqual(interp.env.get_local("X"), 7)
        self.assertIsNone(gen.gi_frame)

    def test_exhaustion_preserves_permanent_head_effects(self):
        interp = PlannerInterpreter()
        interp.env.push_frame(["F"], {"F": "ORIGINAL"})
        source = "[[ALT [PSET F +] [PSET F -]] 5 2]"
        node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
        self.assertEqual(list(interp.eval_form_bt(node)), [7, 3])
        self.assertEqual(interp.env.get_local("F"), "-")
        self.assertEqual(len(interp.env._frames), 1)


class TestSpecialFormStreams(unittest.TestCase):

    def test_quote_and_define_allow_enclosing_alternatives_to_resume(self):
        cases = (
            ("[ALT [QUOTE [FAIL]] 7]", ["[FAIL]", "7"]),
            ("[ALT <QUOTE (A B)> 7]", ["(A B)", "7"]),
            ("[ALT [DEFINE MYIDENTITY (LAMBDA (X) .X)] [MYIDENTITY 9]]",
             ["MYIDENTITY", "9"]),
            ("[ALT <DEFINE MYIDENTITY (LAMBDA (X) .X)> [MYIDENTITY 9]]",
             ["(MYIDENTITY)", "9"]),
            ("[ALT [DEFINE MYNINE (KAPPA () 9)] [IS [MYNINE] 9]]",
             ["MYNINE", "T"]),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                interp = PlannerInterpreter()
                node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
                self.assertEqual([codec.repr_value(value, interp._float_digits)
                                  for value in interp.eval_form_bt(node)], expected)
                self.assertEqual(len(interp.env._frames), 0)

    def test_invalid_quote_and_define_raise_runtime_errors(self):
        for source in ("[QUOTE]", "[QUOTE A B]", "[DEFINE]", "[DEFINE F (WRONG () 1)]"):
            with self.subTest(source=source):
                interp = PlannerInterpreter()
                node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
                with self.assertRaises(PlannerRuntimeError):
                    list(interp.eval_form_bt(node))
                self.assertEqual(interp._functions, {})


class TestNestedAlternatives(unittest.TestCase):

    def test_transparent_evaluation_preserves_alternatives(self):
        cases = (
            ("[DEFINE MYIDENTITY (LAMBDA (X) .X)] [MYIDENTITY [AMONG (1 2)]]", ["1", "2"]),
            ("[DEFINE MYARGS (LAMBDA X .X)] [MYARGS [AMONG (1 2)]]", ["(1)", "(2)"]),
            ("[DEFINE MYSUB (LAMBDA (X Y) [- .X .Y])] [MYSUB [AMONG (5 6)] [AMONG (1 2)]]",
             ["4", "3", "5", "4"]),
            ("([AMONG (1 2)] [AMONG (A B)])", ["(1 A)", "(1 B)", "(2 A)", "(2 B)"]),
            ("[FORM [AMONG (1 2)] <AMONG ((A B) (C))>]", ["(1 A B)", "(1 C)", "(2 A B)", "(2 C)"]),
            ("[EVAL [QUOTE [AMONG (1 2)]]]", ["1", "2"]),
            ("[ALT [AMONG (1 2)] 3]", ["1", "2", "3"]),
            ("[FP POINT [AMONG (1 2)] 3]", ["1", "2", "3"]),
            ("[AMONG [AMONG ((1 2) (3 4))]]", ["1", "2", "3", "4"]),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                interp = PlannerInterpreter()
                program = PlannerParser().parse(Lexer(source).tokenize())
                for definition in program.forms[:-1]:
                    interp.eval_form(definition)
                gen = interp.eval_form_bt(program.forms[-1])
                try:
                    self.assertEqual([codec.repr_value(value, interp._float_digits)
                                      for value in gen], expected)
                    self.assertIsNone(gen.gi_frame)
                    self.assertEqual(len(interp.env._frames), 0)
                finally:
                    gen.close()

    def test_gate_explicitly_accepts_first_success(self):
        interp = PlannerInterpreter()
        node = PlannerParser().parse(Lexer("[GATE [AMONG (1 2)]]").tokenize()).forms[0]
        self.assertEqual(list(interp.eval_form_bt(node)), [1])
        self.assertEqual(len(interp.env._frames), 0)

    def test_nested_stream_lifetime_and_effects(self):
        expressions = (
            "[MYIDENTITY [ALT [SET X 1] [SET X 2]]]",
            "[EVAL [QUOTE [ALT [SET X 1] [SET X 2]]]]",
            "([ALT [SET X 1] [SET X 2]])",
            "[FORM [ALT [SET X 1] [SET X 2]]]",
            "[ALT [AMONG ([SET X 1] [SET X 2])]]",
        )
        for source in expressions:
            for accept in (True, False):
                with self.subTest(source=source, accept=accept):
                    interp = PlannerInterpreter()
                    interp.env.push_frame(["X", "P"], {"X": 0, "P": 0})
                    definition = PlannerParser().parse(Lexer(
                        "[DEFINE MYIDENTITY (LAMBDA (ARG) .ARG)]").tokenize()).forms[0]
                    interp.eval_form(definition)
                    node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
                    gen = interp.eval_form_bt(node)
                    try:
                        next(gen)
                        # При построении списка оба SET выполняются до выбора элемента через AMONG.
                        first_x = 2 if source.startswith("[ALT [AMONG") else 1
                        self.assertEqual(interp.env.get_local("X"), first_x)
                        permanent = PlannerParser().parse(Lexer("[PSET P 9]").tokenize()).forms[0]
                        interp.eval_form(permanent)
                        if accept:
                            gen.close()
                            self.assertEqual(interp.env.get_local("X"), first_x)
                        else:
                            next(gen)
                            with self.assertRaises(StopIteration):
                                next(gen)
                            self.assertEqual(interp.env.get_local("X"), 0)
                        self.assertEqual(interp.env.get_local("P"), 9)
                        self.assertEqual(len(interp.env._frames), 1)
                        self.assertIsNone(gen.gi_frame)
                    finally:
                        gen.close()


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


class TestGO(unittest.TestCase):

    def test_nested_go_preserves_choices_before_enclosing_form(self):
        jump_forms = (
            "[GO OUT]",
            "[COND (T [GO OUT])]",
            "[COND (T [COND (T [GO OUT])])]",
            "[DO [GO OUT]]",
            "[GATE [GO OUT]]",
        )
        for jump in jump_forms:
            with self.subTest(jump=jump):
                source = f"""
                [PROG (X)
                    [SET X [AMONG (A B)]]
                    {jump}
                    [FAIL]
                    OUT
                    [UNFALSE [EQ .X B]]
                    .X]
                """
                self.assertEqual(_eval_last(source), "B")

    def test_do_preserves_choices_without_go(self):
        source = """
        [PROG (X)
            [DO [SET X [AMONG (A B)]]]
            [UNFALSE [EQ .X B]]
            .X]
        """
        self.assertEqual(_eval_last(source), "B")

    # Известный дефект: GoSignal закрывает генераторы внутри DO
    # до того, как внешний PROG сможет сохранить их продолжения.
    @unittest.expectedFailure
    def test_go_from_do_preserves_choices_after_failure(self):
        """После перехода наружу отказ для A должен возобновить AMONG с B."""
        source = """
        [PROG (X)
            [DO
                [SET X [AMONG (A B)]]
                [GO OUT]]
            [FAIL]
            OUT
            [UNFALSE [EQ .X B]]
            .X]
        """
        self.assertEqual(_eval_last(source), "B")

    # Известный дефект: GoSignal завершает цепочку _eval_body_bt внутри GATE.
    @unittest.expectedFailure
    def test_go_to_outer_prog_preserves_gate_choices_after_failure(self):
        """Переход из GATE не должен уничтожать созданную внутри развилку."""
        source = """
        [PROG (X)
            [GATE
                [SET X [AMONG (A B)]]
                [GO OUT]]
            [FAIL]
            OUT
            [UNFALSE [EQ .X B]]
            .X]
        """
        self.assertEqual(_eval_last(source), "B")

    # Известный дефект: выход из DO через GO теряет второе решение.
    @unittest.expectedFailure
    def test_go_from_do_preserves_all_choices(self):
        """FIND должен собрать обе альтернативы, созданные до выхода из DO."""
        source = """
        [FIND ALL (R) .R
            [SET R
                [PROG (X)
                    [DO
                        [SET X [AMONG (A B)]]
                        [GO OUT]]
                    [FAIL]
                    OUT
                    .X]]]
        """
        self.assertEqual(_eval_last(source), "(B A)")


class TestProgContinuations(unittest.TestCase):

    def test_suspended_prog_does_not_shadow_sibling_argument(self):
        source = "[PROG ((X 100)) [+ [PROG ((X 5)) .X] .X]]"
        self.assertEqual(_eval_last(source), "105")

    def test_prog_scope_is_restored_on_resume_and_close(self):
        for result_form in (".X", "[RETURN .X]"):
            for accept in (True, False):
                with self.subTest(result_form=result_form, accept=accept):
                    interp = PlannerInterpreter()
                    frame = interp.env.push_frame(["X", "P"], {"X": 100, "P": 0})
                    source = f"""
                    [+ [PROG ((X 0))
                        [SET X [AMONG (5 6)]]
                        [PSET P .X]
                        {result_form}] .X]
                    """
                    node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
                    gen = interp.eval_form_bt(node)
                    try:
                        self.assertEqual(next(gen), 105)
                        self.assertEqual(len(interp.env._frames), 1)
                        self.assertIs(interp.env._frames[0], frame)
                        self.assertEqual(interp.env.get_local("X"), 100)
                        if accept:
                            gen.close()
                            self.assertEqual(interp.env.get_local("P"), 5)
                        else:
                            self.assertEqual(next(gen), 106)
                            with self.assertRaises(StopIteration):
                                next(gen)
                            self.assertEqual(interp.env.get_local("P"), 6)
                        self.assertEqual(len(interp.env._frames), 1)
                        self.assertIs(interp.env._frames[0], frame)
                        self.assertEqual(interp.env.get_local("X"), 100)
                        self.assertIsNone(gen.gi_frame)
                    finally:
                        gen.close()

    def test_named_failure_reaches_owning_fp(self):
        self.assertEqual(_eval_last("[FP STOP [PROG () [FAIL OOPS STOP]] 9]"), "9")

    def test_client_next_resumes_choices_after_and_before_go(self):
        source = """
        [PROG (X)
            [SET X [AMONG (1 2)]]
            [GO OUT]
            [FAIL]
            OUT
            [+ .X [AMONG (10 20)]]]
        """
        interp = PlannerInterpreter()
        node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
        gen = interp.eval_form_bt(node)
        try:
            for expected in (11, 21, 12, 22):
                self.assertEqual(next(gen), expected)
            with self.assertRaises(StopIteration):
                next(gen)
            self.assertEqual(interp.env._frames, [])
            self.assertIsNone(gen.gi_frame)
        finally:
            gen.close()

    def test_failure_finds_another_choice_in_the_same_next(self):
        source = "[PROG (X) [SET X [AMONG (1 2)]] [UNFALSE [EQ .X 2]] .X]"
        interp = PlannerInterpreter()
        node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
        gen = interp.eval_form_bt(node)
        try:
            self.assertEqual(next(gen), 2)
        finally:
            gen.close()
        self.assertEqual(interp.env._frames, [])
        self.assertIsNone(gen.gi_frame)

    def test_return_alternatives_do_not_execute_following_forms(self):
        interp = PlannerInterpreter()
        source = "[PROG () [RETURN [AMONG (10 20)]] [UNKNOWN]]"
        node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
        self.assertEqual(list(interp.eval_form_bt(node)), [10, 20])
        self.assertEqual(interp.env._frames, [])
        self.assertEqual(len(interp.env._frames), 0)

    def test_close_accepts_effects_and_exhaustion_undoes_them(self):
        for accept in (True, False):
            with self.subTest(accept=accept):
                interp = PlannerInterpreter()
                frame = interp.env.push_frame(["X", "P"], {"X": 0, "P": 0})
                source = """
                [PROG ()
                    [SET X [AMONG (1 2)]]
                    [PSET P .X]
                    [DO [GO OUT]]
                    [UNKNOWN]
                    OUT .X]
                """
                node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
                gen = interp.eval_form_bt(node)
                try:
                    self.assertEqual(next(gen), 1)
                    if accept:
                        gen.close()
                        self.assertEqual(interp.env.get_local("X"), 1)
                        self.assertEqual(interp.env.get_local("P"), 1)
                    else:
                        self.assertEqual(next(gen), 2)
                        with self.assertRaises(StopIteration):
                            next(gen)
                        self.assertEqual(interp.env.get_local("X"), 0)
                        self.assertEqual(interp.env.get_local("P"), 2)
                    self.assertEqual(len(interp.env._frames), 1)
                    self.assertIs(interp.env._frames[0], frame)
                    self.assertIsNone(gen.gi_frame)
                finally:
                    gen.close()

    def test_runtime_error_closes_suspended_generators_and_frames(self):
        interp = PlannerInterpreter()
        source = "[PROG (X) [SET X [AMONG (1 2)]] [DO [GO OUT]] OUT [UNKNOWN]]"
        node = PlannerParser().parse(Lexer(source).tokenize()).forms[0]
        with self.assertRaises(PlannerRuntimeError):
            list(interp.eval_form_bt(node))
        self.assertEqual(interp.env._frames, [])
        self.assertEqual(len(interp.env._frames), 0)


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
