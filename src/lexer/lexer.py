import re
from collections.abc import Generator

from src.lexer.models import (
    TT,
    Token,
    OPEN_TO_CLOSE,
    OPEN_BRACKETS,
    CLOSE_BRACKETS,
    BRACKETS,
    DELIMITERS,
    PREFIX_TYPES,
)


class LexerError(Exception):
    """Ошибка лексического анализа."""


def is_delimiter(ch: str) -> bool:
    return ch in DELIMITERS


def is_digit(ch: str) -> bool:
    return ord('0') <= ord(ch) <= ord('9')


def is_letter(ch: str) -> bool:
    return not is_delimiter(ch) and not is_digit(ch)


def is_identifier(word: str) -> bool:
    return is_letter(word[0]) and all(ch not in BRACKETS for ch in word)


_FLOAT_RE = re.compile(r'[+-]?\d+\.\d*')   # 2.71828, -0.5, +6.
_INT_RE   = re.compile(r'[+-]?\d+')         # 42, -9, +3000000
_SCALE_RE = re.compile(r'\*[0-7]+')         # *5, *3704


def _classify(word: str, line: int, col: int) -> list[Token]:
    """Определить тип(ы) токена для выделенного слова.

    Возвращает список из одного токена для большинства слов или двух токенов,
    когда слово содержит префикс ссылки на переменную (DOT/STAR/COLON/BANG-*).
    """

    # 1. Bang-варианты: !. !* !:  →  BANG_xx + IDENT
    for prefix, tt in [('!.', TT.BANG_DOT), ('!*', TT.BANG_STAR), ('!:', TT.BANG_COLON)]:
        if word.startswith(prefix):
            name = word.removeprefix(prefix)
            if not name or not is_letter(name[0]):
                raise LexerError(
                    f"Ожидается имя переменной после {prefix!r} "
                    f"в строке {line}, столбец {col}"
                )
            if not is_identifier(name):
                raise LexerError(
                    f"Недопустимое имя переменной {name!r} "
                    f"в строке {line}, столбец {col}"
                )
            return [
                Token(tt, prefix, line, col),
                Token(TT.IDENT, name, line, col + len(prefix)),
            ]

    # 2. Префиксы ссылок на переменные
    if word.startswith('.'):
        if len(word) == 1:
            # Одиночный спецлитер → идентификатор
            return [
                Token(TT.IDENT, '.', line, col),
            ]
        name = word.removeprefix('.')
        if not name or not is_identifier(name):
            raise LexerError(
                f"Недопустимое имя переменной {name!r} "
                f"в строке {line}, столбец {col}"
            )
        return [
            Token(TT.DOT, '.', line, col),
            Token(TT.IDENT, name, line, col + 1),
        ]

    if word.startswith(':'):
        if len(word) == 1:
            # Одиночный спецлитер → идентификатор
            return [
                Token(TT.IDENT, ':', line, col),
            ]
        name = word.removeprefix(':')
        if not name or not is_identifier(name):
            raise LexerError(
                f"Недопустимое имя переменной {name!r} "
                f"в строке {line}, столбец {col}"
            )
        return [
            Token(TT.COLON, ':', line, col),
            Token(TT.IDENT, name, line, col + 1),
        ]

    if word.startswith('*'):
        if len(word) == 1:
            # Одиночный спецлитер → идентификатор
            return [
                Token(TT.IDENT, '*', line, col),
            ]
        
        if _SCALE_RE.fullmatch(word):
            return [
                Token(TT.SCALE, word, line, col)
            ]

        name = word.removeprefix('*')
        if not name or not is_identifier(name):
            raise LexerError(
                f"Недопустимое имя переменной {name!r} "
                f"в строке {line}, столбец {col}"
            )
        return [
            Token(TT.STAR, '*', line, col),
            Token(TT.IDENT, name, line, col + 1),
        ]

    # 3. Числовые токены
    if _FLOAT_RE.fullmatch(word):
        return [Token(TT.FLOAT, word, line, col)]
    if _INT_RE.fullmatch(word):
        return [Token(TT.INT, word, line, col)]

    # 4. Идентификатор: +, -, !ABC, ABC, A+B, ×, ...
    if is_identifier(word):
        return [
            Token(TT.IDENT, word, line, col)
        ]
    raise LexerError(
        f"Недопустимое имя переменной {word!r} "
        f"в строке {line}, столбец {col}"
    )


def _split_tokens_into_forms(tokens: list[Token]) -> list[list[Token]]:
    brackets_stack: list[TT] = []
    forms: list[list[Token]] = []
    current_form: list[Token] = []
    expect_ident_after_prefix = False

    for token in tokens:
        # На верхнем уровне каждый новый токен начинает новую форму,
        # кроме IDENT, завершающего пару prefix+IDENT.
        if not brackets_stack and not expect_ident_after_prefix and current_form:
            forms.append(current_form)
            current_form = []

        current_form.append(token)

        if expect_ident_after_prefix:
            if token.type != TT.IDENT:
                raise LexerError(
                    f"Ожидается идентификатор после префикса "
                    f"в строке {token.line}, столбец {token.col}"
                )
            expect_ident_after_prefix = False
            continue

        if token.type in OPEN_BRACKETS:
            brackets_stack.append(token.type)
        elif token.type in CLOSE_BRACKETS:
            if not brackets_stack:
                raise LexerError(
                    f"Несогласованная закрывающая скобка "
                    f"в строке {token.line}, столбец {token.col}"
                )

            expected_close = OPEN_TO_CLOSE[brackets_stack[-1]]
            if token.type != expected_close:
                raise LexerError(
                    f"Несоответствие скобок "
                    f"в строке {token.line}, столбец {token.col}"
                )

            brackets_stack.pop()
            if not brackets_stack:
                forms.append(current_form)
                current_form = []

        elif token.type in PREFIX_TYPES:
            expect_ident_after_prefix = True

    if current_form:
        forms.append(current_form)
    
    if brackets_stack:
        raise LexerError(
            f"Несогласованная открывающая скобка "
            f"в строке {token.line}, столбец {token.col}"
        )

    return forms


class Lexer:
    def __init__(self, source: str) -> None:
        self._src = source

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def tokenize(self) -> list[list[Token]]:
        return _split_tokens_into_forms(list(self._token_stream()))

    # ------------------------------------------------------------------
    # Inner methods
    # ------------------------------------------------------------------

    def _token_stream(self) -> Generator[Token, None, None]:
        src = self._src
        n = len(src)
        pos = 0
        line = 1
        line_start = 0

        while pos < n:
            ch = src[pos]

            # Пропустить пробельные символы (не скобки)
            if ch in ' \t\r':
                pos += 1
                continue
            if ch == '\n':
                line += 1
                line_start = pos + 1
                pos += 1
                continue

            col = pos - line_start + 1

            if ch in BRACKETS:
                yield Token(TT(ch), ch, line, col)
                pos += 1
                continue

            end = pos
            while end < n and not is_delimiter(src[end]):
                end += 1
            word = src[pos:end]
            pos = end

            yield from _classify(word, line, col)
