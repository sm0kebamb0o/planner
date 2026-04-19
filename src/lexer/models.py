from enum import StrEnum, auto
from dataclasses import dataclass


class TT(StrEnum):
    IDENT      = auto()   # идентификатор: ABC, +, ×, =A+B=
    INT        = auto()   # целое число:   42, -9, +3000000
    FLOAT      = auto()   # вещественное:  2.71828, -0.5, +6.
    SCALE      = auto()   # шкала:         *5, *3704
    LPAREN     = '('
    RPAREN     = ')'
    LBRACKET   = '['
    RBRACKET   = ']'
    LANGLE     = '<'
    RANGLE     = '>'
    DOT        = '.'
    STAR       = '*'
    COLON      = ':'
    BANG_DOT   = '!.'
    BANG_STAR  = '!*'
    BANG_COLON = '!:'
    EOF        = 'EOF'


class SpecialSymbols(StrEnum):
    PLUS       = '+'
    MINUS      = '-'
    SPACE      = ' '
    TAB        = '\t'
    NEWLINE    = '\n'
    RETURN     = '\r'


@dataclass
class Token:
    type   : TT
    value  : str
    line   : int
    col    : int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"


DELIMITERS: frozenset[str] = frozenset(
    [
        SpecialSymbols.SPACE,
        SpecialSymbols.TAB,
        SpecialSymbols.NEWLINE,
        SpecialSymbols.RETURN,
        TT.LPAREN,
        TT.RPAREN,
        TT.LBRACKET,
        TT.RBRACKET,
        TT.LANGLE,
        TT.RANGLE,
    ]
)


SPECLITERS = frozenset[str](
    [
        SpecialSymbols.MINUS,
        SpecialSymbols.PLUS,
        TT.DOT,
        TT.STAR,
        TT.COLON,
        TT.BANG_DOT,
        TT.BANG_STAR,
        TT.BANG_COLON,
    ]
)


OPEN_TO_CLOSE: dict[TT, TT] = {
    TT.LPAREN:   TT.RPAREN,
    TT.LBRACKET: TT.RBRACKET,
    TT.LANGLE:   TT.RANGLE,
}


OPEN_BRACKETS = frozenset[TT](OPEN_TO_CLOSE.keys())


CLOSE_BRACKETS = frozenset[TT](OPEN_TO_CLOSE.values())


BRACKETS = OPEN_BRACKETS | CLOSE_BRACKETS


PREFIX_TYPES = frozenset({
    TT.DOT, TT.STAR, TT.COLON,
    TT.BANG_DOT, TT.BANG_STAR, TT.BANG_COLON,
})