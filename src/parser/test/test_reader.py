"""
Тесты синтаксического анализатора языка Плэннер (PlannerReader).

Запуск:
    cd /Users/mt1mur/Documents/CMC/planner
    python -m pytest src/parser/test/test_reader.py -v
    # или напрямую:
    python src/parser/test/test_reader.py
"""

import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import unittest

from src.lexer import Lexer
from src.parser import (
    PlannerReader, ParseError,
    ProgramNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)


def _parse(source: str) -> ProgramNode:
    """Вспомогательная функция: токенизировать и разобрать строку."""
    groups = Lexer(source).tokenize()
    return PlannerReader().read(groups)


def _form(source: str):
    """Вернуть первую (единственную) форму разобранной программы."""
    return _parse(source).forms[0]


class TestAtomParsing(unittest.TestCase):
    """Разбор атомарных форм."""

    def test_ident(self):
        node = _form("ABC")
        self.assertIsInstance(node, IdentNode)
        self.assertEqual(node.name, "ABC")

    def test_int_unsigned(self):
        node = _form("42")
        self.assertIsInstance(node, IntNode)
        self.assertEqual(node.value, 42)

    def test_int_negative(self):
        node = _form("-9")
        self.assertIsInstance(node, IntNode)
        self.assertEqual(node.value, -9)

    def test_float(self):
        node = _form("2.71828")
        self.assertIsInstance(node, FloatNode)
        self.assertAlmostEqual(node.value, 2.71828)

    def test_scale(self):
        node = _form("*3704")
        self.assertIsInstance(node, ScaleNode)
        self.assertEqual(node.source, "3704")
        self.assertEqual(node.bits, int("3704", 8))


class TestVarRefParsing(unittest.TestCase):
    """Разбор ссылок на переменные."""

    def test_dot_read(self):
        node = _form(".X")
        self.assertIsInstance(node, VarRefNode)
        self.assertEqual(node.mode, VarMode.READ)
        self.assertEqual(node.name, "X")
        self.assertFalse(node.segmented)

    def test_star_assign(self):
        node = _form("*X")
        self.assertIsInstance(node, VarRefNode)
        self.assertEqual(node.mode, VarMode.ASSIGN)

    def test_colon_const(self):
        node = _form(":PI")
        self.assertIsInstance(node, VarRefNode)
        self.assertEqual(node.mode, VarMode.CONST)
        self.assertEqual(node.name, "PI")

    def test_bang_dot_segmented(self):
        node = _form("!.X")
        self.assertIsInstance(node, VarRefNode)
        self.assertTrue(node.segmented)


class TestLListParsing(unittest.TestCase):
    """Разбор L-списков (круглые скобки)."""

    def test_empty_list(self):
        node = _form("()")
        self.assertIsInstance(node, LListNode)
        self.assertEqual(node.elements, [])

    def test_simple_list(self):
        node = _form("(A B C)")
        self.assertIsInstance(node, LListNode)
        self.assertEqual(len(node.elements), 3)
        self.assertIsInstance(node.elements[0], IdentNode)

    def test_nested_list(self):
        node = _form("((1 2) (3 4))")
        self.assertIsInstance(node, LListNode)
        self.assertEqual(len(node.elements), 2)
        self.assertIsInstance(node.elements[0], LListNode)


class TestCallParsing(unittest.TestCase):
    """Разбор вызовов функций (P-списки и S-списки)."""

    def test_simple_call(self):
        node = _form("[+ 1 2]")
        self.assertIsInstance(node, CallNode)
        self.assertFalse(node.segmented)
        self.assertIsInstance(node.head, IdentNode)
        self.assertEqual(node.head.name, "+")
        self.assertEqual(len(node.args), 2)

    def test_call_no_args(self):
        node = _form("[READ]")
        self.assertIsInstance(node, CallNode)
        self.assertEqual(len(node.args), 0)

    def test_segmented_call(self):
        node = _form("<REST 1 (A B C)>")
        self.assertIsInstance(node, CallNode)
        self.assertTrue(node.segmented)

    def test_nested_call(self):
        node = _form("[+ [× 2 3] 1]")
        self.assertIsInstance(node, CallNode)
        self.assertIsInstance(node.args[0], CallNode)

    def test_call_with_varref(self):
        node = _form("[+ .X .Y]")
        self.assertIsInstance(node, CallNode)
        self.assertIsInstance(node.args[0], VarRefNode)


class TestProgramParsing(unittest.TestCase):
    """Разбор программ с несколькими формами."""

    def test_multiple_forms(self):
        prog = _parse("ABC 42 [+ 1 2]")
        self.assertEqual(len(prog.forms), 3)

    def test_define_and_call(self):
        prog = _parse("[DEFINE SQUARE (LAMBDA (N) [× .N .N])]\n[SQUARE 7]")
        self.assertEqual(len(prog.forms), 2)
        self.assertIsInstance(prog.forms[0], CallNode)
        self.assertIsInstance(prog.forms[1], CallNode)

    def test_comment_atoms(self):
        prog = _parse("* это комментарий-атом\n[+ 1 2]")
        # «*» — атом, остальные слова тоже атомы; последняя форма — вызов
        self.assertIsInstance(prog.forms[-1], CallNode)


class TestParseErrors(unittest.TestCase):
    """Ошибки синтаксического анализа."""

    def test_empty_brackets(self):
        # [] — пустой P-список без головы, должен быть ошибкой
        with self.assertRaises(ParseError):
            _parse("[]")

    def test_unclosed_bracket(self):
        # незакрытая скобка приводит к ошибке в лексере или парсере
        with self.assertRaises(Exception):
            _parse("[+ 1 2")


class TestTestProgram(unittest.TestCase):
    """Разбор тестовой программы из файла."""

    def test_parse_test_program(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_program.pl")
        if not os.path.isfile(test_file):
            self.skipTest("test_program.pl not found")
        with open(test_file, encoding="utf-8") as f:
            source = f.read()
        prog = _parse(source)
        self.assertGreater(len(prog.forms), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
