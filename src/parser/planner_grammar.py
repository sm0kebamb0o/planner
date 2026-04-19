from .models import Terminal, Neterminal
from .grammar import Grammar


_TERMINAL_NAMES = [
    "IDENT",
    "INT",
    "FLOAT",
    "SCALE",
    "LPAREN",
    "RPAREN",
    "LBRACKET",
    "RBRACKET",
    "LANGLE",
    "RANGLE",
    "DOT",
    "STAR",
    "COLON",
    "BANG_DOT",
    "BANG_STAR",
    "BANG_COLON",
]

TERMINALS: list[Terminal] = [Terminal(name) for name in _TERMINAL_NAMES]

_NONTERMINAL_NAMES = [
    "Program",
    "FormList",
    "ArgList",
    "Form",
    "Atom",
    "VarRef",
    "LList",
    "PList",
    "SList",
]

NON_TERMINALS: list[Neterminal] = [Neterminal(name) for name in _NONTERMINAL_NAMES]


_GRAMMAR_TEXT = """
Program  -> FormList

FormList -> Form FormList | eps

ArgList  -> Form ArgList | eps

Form     -> Atom | VarRef | LList | PList | SList

Atom     -> IDENT | INT | FLOAT | SCALE

VarRef   -> DOT        IDENT
VarRef   -> STAR       IDENT
VarRef   -> COLON      IDENT
VarRef   -> BANG_DOT   IDENT
VarRef   -> BANG_STAR  IDENT
VarRef   -> BANG_COLON IDENT

LList    -> LPAREN   FormList RPAREN
PList    -> LBRACKET Form ArgList RBRACKET
SList    -> LANGLE   Form ArgList RANGLE
"""

# TODO: Грамматика все-таки неправильная, так как в угловых скобках может быть не форма


def build_planner_grammar() -> Grammar:
    """Return the Planner CFG ready to be passed to Graph.from_grammar()."""
    return Grammar.parse(
        text=_GRAMMAR_TEXT,
        terminals=TERMINALS,
        non_terminals=NON_TERMINALS,
        start=NON_TERMINALS[0],  # Program
    )
