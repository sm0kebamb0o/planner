"""
Тесты лексического анализатора языка Плэннер.

Запуск:
    cd /Users/mt1mur/Documents/CMC/planner
    python -m pytest src/lexer/test/test_lexer.py -v
    # или напрямую:
    python src/lexer/test/test_lexer.py
"""

import unittest

from src.lexer import Lexer, LexerError


def _flat(source: str) -> list[tuple[str, str]]:
    """Токенизировать строку и вернуть плоский список (тип, значение)."""
    groups = Lexer(source).tokenize()
    return [(t.type.name, t.value) for g in groups for t in g]


def _groups(source: str) -> list[list[tuple[str, str]]]:
    """Токенизировать строку и вернуть список групп (тип, значение)."""
    return [[(t.type.name, t.value) for t in g] for g in Lexer(source).tokenize()]


class TestAtoms(unittest.TestCase):
    """Атомарные токены: IDENT, INT, FLOAT, SCALE."""

    def test_ident_simple(self):
        self.assertEqual(_flat("ABC"), [("IDENT", "ABC")])

    def test_ident_with_specials(self):
        self.assertEqual(_flat("+"), [("IDENT", "+")])
        self.assertEqual(_flat("-"), [("IDENT", "-")])

    def test_ident_mixed(self):
        self.assertEqual(_flat("A+B"), [("IDENT", "A+B")])

    def test_int_positive(self):
        self.assertEqual(_flat("42"), [("INT", "42")])

    def test_int_negative(self):
        self.assertEqual(_flat("-9"), [("INT", "-9")])

    def test_int_explicit_plus(self):
        self.assertEqual(_flat("+3"), [("INT", "+3")])

    def test_float(self):
        self.assertEqual(_flat("2.71828"), [("FLOAT", "2.71828")])

    def test_float_negative(self):
        self.assertEqual(_flat("-0.5"), [("FLOAT", "-0.5")])

    def test_float_trailing_dot(self):
        result = _flat("+6.")
        self.assertEqual(result[0][0], "FLOAT")

    def test_scale(self):
        self.assertEqual(_flat("*3704"), [("SCALE", "*3704")])

    def test_scale_minimal(self):
        self.assertEqual(_flat("*5"), [("SCALE", "*5")])


class TestBrackets(unittest.TestCase):
    """Скобки всех трёх видов."""

    def test_round(self):
        result = _flat("(A)")
        self.assertEqual(result[0], ("LPAREN", "("))
        self.assertEqual(result[-1], ("RPAREN", ")"))

    def test_square(self):
        result = _flat("[+ 1 2]")
        self.assertEqual(result[0], ("LBRACKET", "["))
        self.assertEqual(result[-1], ("RBRACKET", "]"))

    def test_angle(self):
        result = _flat("<REST 1 (A B)>")
        self.assertEqual(result[0], ("LANGLE", "<"))
        self.assertEqual(result[-1], ("RANGLE", ">"))


class TestVarRef(unittest.TestCase):
    """Ссылки на переменные: DOT, STAR, COLON и их ! варианты."""

    def test_dot_read(self):
        self.assertEqual(_flat(".X"), [("DOT", "."), ("IDENT", "X")])

    def test_star_assign(self):
        self.assertEqual(_flat("*X"), [("STAR", "*"), ("IDENT", "X")])

    def test_colon_const(self):
        self.assertEqual(_flat(":PI"), [("COLON", ":"), ("IDENT", "PI")])

    def test_bang_dot(self):
        result = _flat("!.X")
        self.assertEqual(result[0][0], "BANG_DOT")

    def test_bang_star(self):
        result = _flat("!*X")
        self.assertEqual(result[0][0], "BANG_STAR")

    def test_bang_colon(self):
        result = _flat("!:C")
        self.assertEqual(result[0][0], "BANG_COLON")


class TestSplitIntoForms(unittest.TestCase):
    """Разбивка токенов на формы верхнего уровня."""

    def test_single_atom(self):
        groups = _groups("ABC")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0], [("IDENT", "ABC")])

    def test_two_atoms(self):
        groups = _groups("ABC DEF")
        self.assertEqual(len(groups), 2)

    def test_bracket_expression(self):
        groups = _groups("[+ 1 2]")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0], ("LBRACKET", "["))
        self.assertEqual(groups[0][-1], ("RBRACKET", "]"))

    def test_varref_two_tokens(self):
        groups = _groups(":PI")
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)
        self.assertEqual(groups[0][0][0], "COLON")
        self.assertEqual(groups[0][1][0], "IDENT")

    def test_nested_brackets(self):
        groups = _groups("[LENGTH (A B C D)]")
        self.assertEqual(len(groups), 1)
        all_tokens = groups[0]
        self.assertEqual(all_tokens[0], ("LBRACKET", "["))
        self.assertEqual(all_tokens[-1], ("RBRACKET", "]"))

    def test_multiple_forms(self):
        groups = _groups("ABC [+ 1 2] :PI")
        self.assertEqual(len(groups), 3)

    def test_empty_list(self):
        groups = _groups("()")
        self.assertEqual(len(groups), 1)

    def test_mismatched_bracket(self):
        with self.assertRaises(LexerError):
            Lexer(")").tokenize()


class TestLineNumbers(unittest.TestCase):
    """Позиции токенов (строка, столбец)."""

    def test_line_number(self):
        groups = Lexer("ABC\nDEF").tokenize()
        self.assertEqual(groups[0][0].line, 1)
        self.assertEqual(groups[1][0].line, 2)

    def test_col_number(self):
        groups = Lexer("[+ 1 2]").tokenize()
        flat = [t for g in groups for t in g]
        self.assertEqual(flat[0].col, 1)   # [
        self.assertEqual(flat[1].col, 2)   # +


if __name__ == "__main__":
    unittest.main(verbosity=2)
