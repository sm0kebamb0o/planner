import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from src.interpreter import PlannerInterpreter, PlannerRuntimeError
from src.interpreter.database import Database, property_map
from src.interpreter.functions import codec
from src.interpreter.signals import PlannerFailure
from src.interpreter.values import BracketKind, NIL, PlannerList
from src.lexer import Lexer
from src.parser import PlannerParser


def parse(source):
    return PlannerParser().parse(Lexer(source).tokenize())


def evaluate(source, interp):
    result = NIL
    for form in parse(source).forms:
        result = interp.eval_form(form)
    return result


class TestDatabaseStorage(unittest.TestCase):
    def test_copy_boundaries_and_identity(self):
        db = Database()
        fact = PlannerList(["P", PlannerList(["A"])])
        props = {"COLOUR": PlannerList(["RED"])}
        entry = db.insert(fact, props)
        fact.elements[1].elements.append("B")
        props["COLOUR"].elements.append("BLUE")
        entry.value.elements.append("C")
        stored = db.get(entry.id)
        self.assertEqual(stored.value, PlannerList(["P", PlannerList(["A"])]))
        self.assertEqual(stored.properties, {"COLOUR": PlannerList(["RED"])})
        stored.properties.clear()
        self.assertEqual(db.get(entry.id).properties, {"COLOUR": PlannerList(["RED"])})

    def test_restore_order_and_preserve_newer_duplicate(self):
        db = Database()
        a = db.insert(PlannerList(["A"]), {"OLD": 1})
        b = db.insert(PlannerList(["B"]), {})
        removed = db.remove(a.id)
        db.restore(removed)
        self.assertEqual(tuple(db.ids()), (a.id, b.id))
        db.remove(a.id)
        replacement = db.insert(a.value, {"NEW": 2})
        db.restore(removed)
        self.assertEqual(db.find(a.value).id, replacement.id)
        self.assertEqual(db.find(a.value).properties, {"NEW": 2})

    def test_properties_normalization(self):
        self.assertEqual(property_map(PlannerList(["A", 1, "A", 2, "B", NIL])), {"A": 2})
        for value in (1, PlannerList(["A"]), PlannerList([1, 2]),
                      PlannerList([], BracketKind.SQUARE)):
            with self.assertRaises(PlannerRuntimeError):
                property_map(value)

    def test_list_kind_and_numeric_equality(self):
        db = Database()
        db.insert(PlannerList([1]), {})
        self.assertIsNone(db.insert(PlannerList([1.0]), {}))
        db.insert(PlannerList([PlannerList(["A"], BracketKind.SQUARE)]), {})
        db.insert(PlannerList([PlannerList(["A"], BracketKind.ROUND)]), {})
        self.assertEqual(sum(1 for _ in db.ids()), 3)




class TestDatabaseLanguage(unittest.TestCase):
    def setUp(self):
        self.interp = PlannerInterpreter()

    def value(self, source):
        return evaluate(source, self.interp)

    def text(self, source):
        return codec.repr_value(self.value(source))

    def assertFailure(self, source, message=None):
        with self.assertRaises(PlannerFailure) as caught:
            self.value(source)
        if message is not None:
            self.assertEqual(caught.exception.message, message)

    def test_empty_search_messages(self):
        self.assertFailure("[SEARCH (P)]", "SEARCH")
        self.assertFailure("[SEARCH1 (P)]", "SEARCH1")

    def test_assert_duplicate_else_and_properties(self):
        self.assertEqual(self.text("[ASSERT (BOX A) (WITH COLOUR RED)]"), "(BOX A)")
        self.assertEqual(self.text("[ASSERT (BOX A) (WITH COLOUR BLUE)]"), "()")
        self.assertEqual(self.text("[GETA (BOX A) COLOUR]"), "RED")
        self.assertEqual(self.text("[ASSERT (BOX A) (ELSE DUP)]"), "DUP")
        self.assertFailure("[ASSERT (BOX A) (ELSE)]")
        self.assertEqual(self.text("[SEARCH (BOX A)]"), "(BOX A)")

    def test_find_all_and_search1(self):
        self.value("[DATA (P A) (P B) (P C)]")
        self.assertEqual(self.text("[FIND ALL (X) .X [SEARCH (P *X)]]"), "(C B A)")
        self.assertEqual(self.text("[FIND ALL (X) .X [SEARCH1 (P *X)]]"), "(A)")
        self.assertEqual(len(self.interp.env._frames), 0)

    def test_filter_rollback_from_book(self):
        self.value("[DB (STUDENT PETROV) (COURSE 4 FACULTY VMK)"
                   " (STUDENT IVANOV) (COURSE 5 FACULTY MECHMAT)]")
        self.assertEqual(self.text(
            "[PROG (X Y) [SEARCH (STUDENT *X)"
            " (TEST COURSE *Y FACULTY [NON VMK])] (.X .Y)]"), "(IVANOV 5)")

    def test_late_mismatch_restores_original_binding(self):
        self.value("[DATA (P A NO) (P B YES)]")
        self.assertEqual(self.text(
            "[PROG ((X OLD)) [SEARCH (P *X YES)] .X]"), "B")
        self.assertEqual(self.text(
            "[PROG ((X OLD)) [GATE [SEARCH (P *X MISSING)]] .X]"), "OLD")

    def test_dot_and_star(self):
        self.value("[DATA (P A) (P B)]")
        self.assertEqual(self.text("[PROG ((X B)) [SEARCH (P .X)] .X]"), "B")
        self.assertEqual(self.text("[PROG ((X B)) [SEARCH (P *X)] .X]"), "A")

    def test_missing_property_is_nil(self):
        self.value("[DATA (BOX A)]")
        self.assertEqual(self.text("[GETA (BOX A) COLOUR]"), "()")
        self.assertEqual(self.text("[SEARCH (BOX A) (TEST COLOUR ())]"), "(BOX A)")
        self.assertFailure("[GETA (BOX B)]", "GETA")

    def test_search1_skips_rejected_candidates(self):
        self.value("[DB (P A) (COLOUR BLUE) (P B) (COLOUR RED)]")
        self.assertEqual(self.text(
            "[PROG (X) [SEARCH1 (P *X) (TEST COLOUR RED)] .X]"), "B")

    def test_stored_patterns_and_wildcards(self):
        self.value("[DATA (P A) (P B)]")
        self.assertEqual(self.text(
            "[PROG (P X) [SET P [QUOTE (P *X)]] [SEARCH .P] .X]"), "A")
        self.assertEqual(self.text(
            "[PROG (P) [SET P [QUOTE (P [])]] [SEARCH .P]]"), "(P A)")
        self.assertEqual(self.text(
            "[PROG (P) [SET P [QUOTE (P [NON A])]] [SEARCH .P]]"), "(P B)")

    def test_stored_segmented_pattern(self):
        self.value("[DATA (P A B)]")
        self.assertEqual(self.text(
            "[PROG (P X) [SET P [QUOTE (P !*X)]] [SEARCH .P] .X]"), "(A B)")

    def test_search_keeps_first_binding_on_close(self):
        self.interp.env.push_frame(["X"], {})
        self.value("[DATA (P A) (P B)]")
        self.assertEqual(self.text("[SEARCH (P *X)]"), "(P A)")
        self.assertEqual(self.interp.env.get_local("X"), "A")
        self.assertEqual(len(self.interp.env._frames), 1)

    def test_search_error_restores_matching_and_test_bindings(self):
        frame = self.interp.env.push_frame(["X", "Y"], {"X": "OLD", "Y": "OLD"})
        self.value("[DB (BOX A) (COLOUR RED)]")
        with self.assertRaisesRegex(PlannerRuntimeError, "Неизвестная функция"):
            self.value("[SEARCH (BOX *X)"
                       " (TEST COLOUR [BE [DO [SET Y NEW] [UNKNOWN]]])]")
        self.assertEqual(frame.bindings, {"X": "OLD", "Y": "OLD"})
        self.assertEqual(len(self.interp.env._frames), 1)

    def test_search_result_is_detached_from_storage(self):
        self.value("[DATA (NEST (A))]")
        found = self.value("[SEARCH (NEST [])]")
        found.elements[1].elements.append("B")
        self.assertEqual(self.text("[SEARCH (NEST (A))]"), "(NEST (A))")

    def test_search_resume_and_exhaustion_restore_state(self):
        self.interp.env.push_frame(["X"], {"X": "OLD"})
        self.value("[DATA (P A) (P B)]")
        gen = self.interp.eval_form_bt(parse("[SEARCH (P *X)]").forms[0])
        self.assertEqual(next(gen), PlannerList(["P", "A"]))
        self.assertEqual(next(gen), PlannerList(["P", "B"]))
        with self.assertRaises(StopIteration):
            next(gen)
        self.assertEqual(self.interp.env.get_local("X"), "OLD")
        self.assertEqual(self.interp._last_failure, "SEARCH")

    def test_late_insertions_excluded_and_removed_candidates_skipped(self):
        self.interp.env.push_frame(["X"], {})
        self.value("[DATA (P A) (P B) (P C)]")
        gen = self.interp.eval_form_bt(parse("[SEARCH (P *X)]").forms[0])
        next(gen)
        self.value("[PERASE (P B)] [PASSERT (P B)] [PASSERT (P D)]")
        self.assertEqual(next(gen), PlannerList(["P", "C"]))
        with self.assertRaises(StopIteration):
            next(gen)
        self.assertEqual(self.text("[FIND ALL (X) .X [SEARCH (P *X)]]"), "(D B C A)")

    def test_properties_are_read_when_candidate_is_checked(self):
        self.interp.env.push_frame(["X"], {})
        self.value("[DB (P A) (COLOUR RED) (P B) (COLOUR BLUE)]")
        gen = self.interp.eval_form_bt(parse(
            "[SEARCH (P *X) (TEST COLOUR RED)]").forms[0])
        self.assertEqual(next(gen), PlannerList(["P", "A"]))
        self.value("[PPUTA (P B) COLOUR RED]")
        self.assertEqual(next(gen), PlannerList(["P", "B"]))
        gen.close()

    def test_undo_does_not_remove_newer_equal_permanent_record(self):
        mark = self.interp._trail.mark()
        self.value("[ASSERT (P A) (WITH VERSION OLD)]")
        self.value("[PERASE (P A)] [PASSERT (P A) (WITH VERSION NEW)]")
        self.interp._trail.undo_to(mark)
        self.assertEqual(self.text("[GETA (P A) VERSION]"), "NEW")

    def test_mutations_rollback_and_permanent_variants(self):
        self.value("[GATE [ASSERT (A)] [FAIL]]")
        self.assertFailure("[SEARCH (A)]")
        self.value("[GATE [PASSERT (A)] [FAIL]]")
        self.assertEqual(self.text("[SEARCH (A)]"), "(A)")
        self.value("[GATE [ERASE (A)] [FAIL]]")
        self.assertEqual(self.text("[SEARCH (A)]"), "(A)")
        self.value("[GATE [PERASE (A)] [FAIL]]")
        self.assertFailure("[SEARCH (A)]")

    def test_permanent_write_does_not_commit_argument_effects(self):
        self.assertEqual(self.text(
            "[PROG ((X OLD)) [GATE [PASSERT (P [SET X NEW])] [FAIL]] .X]"), "OLD")
        self.assertEqual(self.text("[SEARCH (P NEW)]"), "(P NEW)")

    def test_erase_restores_properties_and_order(self):
        self.value("[DB (P A) (COLOUR RED) (P B) ()]")
        self.value("[GATE [ERASE (P A)] [FAIL]]")
        self.assertEqual(self.text("[GETA (P A)]"), "(COLOUR RED)")
        self.assertEqual(self.text("[SEARCH (P [])]"), "(P A)")
        self.assertEqual(self.text("[ERASE (P A) (TEST COLOUR BLUE) (ELSE REJECT)]"), "REJECT")
        self.assertEqual(self.text("[ERASE (MISSING)]"), "()")
        self.assertFailure("[ERASE (MISSING) (ELSE)]")

    def test_property_update_add_delete_rollback(self):
        self.value("[DB (P A) (COLOUR RED)]")
        self.assertEqual(self.text("[PUTA (P A) COLOUR BLUE]"), "BLUE")
        self.value("[GATE [PUTA (P A) COLOUR RED] [FAIL]]")
        self.assertEqual(self.text("[GETA (P A) COLOUR]"), "BLUE")
        self.value("[GATE [PUTA (P A) SIZE 3] [FAIL]]")
        self.assertEqual(self.text("[GETA (P A)]"), "(COLOUR BLUE)")
        self.value("[GATE [PUTA (P A) COLOUR ()] [FAIL]]")
        self.assertEqual(self.text("[GETA (P A) COLOUR]"), "BLUE")
        self.value("[GATE [PPUTA (P A) COLOUR ()] [FAIL]]")
        self.assertEqual(self.text("[GETA (P A)]"), "()")
        self.assertFailure("[PUTA (MISSING) SIZE 3]", "PUTA")
        self.assertFailure("[PPUTA (MISSING) SIZE 3]", "PPUTA")

    def test_data_and_db_return_values_and_partial_failure(self):
        self.assertEqual(self.text("[DATA (A) (B)]"), "(B)")
        self.assertEqual(self.text("[DATA (B)]"), "()")
        self.assertEqual(self.text("[DB (C) (SIZE 3)]"), "(SIZE 3)")
        self.assertEqual(self.text("[DB (C) (SIZE 5)]"), "(SIZE 5)")
        self.assertEqual(self.text("[GETA (C) SIZE]"), "3")
        self.assertFailure("[DATA (D) [FAIL STOP] (E)]", "STOP")
        self.assertEqual(self.text("[SEARCH (D)]"), "(D)")
        self.assertFailure("[SEARCH (E)]")
        self.assertFailure("[DB (F) () (G) [FAIL STOP]]", "STOP")
        self.assertEqual(self.text("[SEARCH (F)]"), "(F)")

    def test_candidates_no_evaluation_or_binding(self):
        self.value("[DB (BOX A) (SIZE 3) (BOX B) ()]")
        self.assertEqual(self.text(
            "[PROG ((X A)) [CANDIDATES (BOX .X)]]"),
            "((BOX A) (SIZE 3) (BOX B) ())")
        self.assertEqual(self.text("[CANDIDATES (BOX [FAIL SHOULD-NOT-RUN])]"),
                         "((BOX A) (SIZE 3) (BOX B) ())")
        self.assertEqual(self.text("[PROG (X) [CANDIDATES (BOX *X)] [HASVAL X]]"), "()")
        self.assertEqual(self.text("[CANDIDATES (BOX []) ASSERT]"),
                         "((BOX A) (SIZE 3) (BOX B) ())")

    def test_candidates_upper_level_lengths_and_segments(self):
        self.value("[DATA (NOT (AT A R1)) (NOT WOMAN) (NOT (X Y))]")
        self.assertEqual(self.text("[CANDIDATES (NOT (IS MAN *X))]"),
                         "((NOT (AT A R1)) ())")
        self.assertEqual(self.text("[CANDIDATES (NOT <>)]"),
                         "((NOT (AT A R1)) () (NOT WOMAN) () (NOT (X Y)) ())")

    def test_variable_predicate_and_nested_matching(self):
        self.value("[DATA (ROOM R1) (DOOR R1) (NEST (A B))]")
        self.assertEqual(self.text("[FIND ALL (P) .P [SEARCH (*P R1)]]"), "(DOOR ROOM)")
        self.assertEqual(self.text("[PROG (X) [SEARCH (NEST (A *X))] .X]"), "B")

    def test_recommendations_rejected_before_effects(self):
        self.value("[DATA (P A)]")
        for source in ("[ASSERT (P B) (TRY)]", "[PASSERT (P B) (USE)]",
                       "[ERASE (P A) (USE1)]", "[PERASE (P A) (FILTER ())]"):
            with self.assertRaisesRegex(PlannerRuntimeError, "пока не поддерживаются"):
                self.value(source)
        self.assertEqual(self.text("[SEARCH (P A)]"), "(P A)")
        self.assertFailure("[SEARCH (P B)]")
        with self.assertRaises(PlannerRuntimeError):
            self.value("[ASSERT [PSET X NEW] (TRY)]")

    def test_invalid_forms(self):
        for source in ("[ASSERT]", "[ASSERT 1]", "[SEARCH 1]", "[SEARCH :P]",
                       "[ASSERT (P) (WITH COLOUR)]", "[DB (P)]",
                       "[DB (P) (1 RED)]", "[SEARCH (P) (TEST COLOUR)]",
                       "[ASSERT (P) (ELSE A B)]", "[GETA (P) 1]",
                       "[CANDIDATES (P) CONSEQ]", "[DATA]", "[DUMP 1]"):
            with self.subTest(source=source), self.assertRaises(PlannerRuntimeError):
                self.value(source)

    def test_dump_output_and_count(self):
        self.value("[DB (P A B) (SIZE 3) (A) () (B) ()]")
        output = io.StringIO()
        with redirect_stdout(output):
            count = self.value("[DUMP]")
        self.assertEqual(count, 3)
        self.assertEqual(output.getvalue(), "(A) ()\n(B) ()\n(P A B) (SIZE 3)\n")

    def test_run_lifetime_and_error_cleanup(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.interp.run(parse("[DATA (P)] [SEARCH (P)]"))
            self.interp.run(parse("[SEARCH (P)]"))
        self.assertIn("=НЕУСПЕХ= SEARCH", output.getvalue())
        self.assertEqual(tuple(self.interp.database.ids()), ())
        with redirect_stdout(output), self.assertRaises(PlannerRuntimeError):
            self.interp.run(parse("[DATA (P)] [UNKNOWN]"))
        self.assertEqual(tuple(self.interp.database.ids()), ())

    def test_undo_binding_after_frame_removed(self):
        frame = self.interp.env.push_frame(["X"], {"X": "OLD"})
        mark = self.interp._trail.mark()
        self.value("[IS *X NEW]")
        self.interp.env.pop_frame()
        other = self.interp.env.push_frame(["X"], {"X": "OTHER"})
        self.interp._trail.undo_to(mark)
        self.assertEqual(frame.bindings["X"], "OLD")
        self.assertEqual(other.bindings["X"], "OTHER")

    def test_documented_example(self):
        source = (Path(__file__).resolve().parents[3] / "examples/database.plan").read_text()
        program = parse(source)
        self.assertEqual(len(program.forms), 6)
        output = io.StringIO()
        with redirect_stdout(output):
            self.interp.run(program)
        self.assertIn("\n(C A)\n", output.getvalue())
        self.assertIn("\n(C 7)\n", output.getvalue())
        self.assertIn("\nRED\n", output.getvalue())
        self.assertTrue(output.getvalue().endswith("\n3\n"))
