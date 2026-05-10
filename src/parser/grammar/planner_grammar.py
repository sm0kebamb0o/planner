from enum import StrEnum

from src.lexer import TT
from ..common.models import Terminal, Neterminal

from .grammar import Grammar, Rule, EPSILON


TerminalName = TT


class NeterminalName(StrEnum):
    PROGRAM   = "Program"
    FORM_LIST = "FormList"
    FORM      = "Form"
    ATOM      = "Atom"
    VAR_REF   = "VarRef"
    L_LIST    = "LList"
    P_LIST    = "PList"
    S_LIST    = "SList"


TERMINALS: dict[TerminalName, Terminal] = {
    t: Terminal(t.name)
    for t in TerminalName
    if t != TerminalName.EOF
}


NETERMINALS: dict[NeterminalName, Neterminal] = {
    nt: Neterminal(nt) for nt in NeterminalName
}


RULES: list[Rule] = [
    Rule(
        lhs=NETERMINALS[NeterminalName.PROGRAM],
        rhs=[
            [NETERMINALS[NeterminalName.FORM_LIST]],
        ]
    ),

    Rule(
        lhs=NETERMINALS[NeterminalName.FORM_LIST],
        rhs=[
            [
                NETERMINALS[NeterminalName.FORM],
                NETERMINALS[NeterminalName.FORM_LIST],
            ],
            [EPSILON],
        ]
    ),

    Rule(
        lhs=NETERMINALS[NeterminalName.FORM],
        rhs=[
            [NETERMINALS[NeterminalName.ATOM]],
            [NETERMINALS[NeterminalName.VAR_REF]],
            [NETERMINALS[NeterminalName.L_LIST]],
            [NETERMINALS[NeterminalName.P_LIST]],
            [NETERMINALS[NeterminalName.S_LIST]],
        ]
    ),

    Rule(
        lhs=NETERMINALS[NeterminalName.ATOM],
        rhs=[
            [TERMINALS[TerminalName.IDENT]],
            [TERMINALS[TerminalName.INT]],
            [TERMINALS[TerminalName.FLOAT]],
            [TERMINALS[TerminalName.SCALE]],
        ]
    ),

    Rule(
        lhs=NETERMINALS[NeterminalName.VAR_REF],
        rhs=[
            [TERMINALS[TerminalName.DOT], TERMINALS[TerminalName.IDENT]],
            [TERMINALS[TerminalName.STAR], TERMINALS[TerminalName.IDENT]],
            [TERMINALS[TerminalName.COLON], TERMINALS[TerminalName.IDENT]],
            [TERMINALS[TerminalName.BANG_DOT], TERMINALS[TerminalName.IDENT]],
            [TERMINALS[TerminalName.BANG_STAR], TERMINALS[TerminalName.IDENT]],
            [TERMINALS[TerminalName.BANG_COLON], TERMINALS[TerminalName.IDENT]],
        ]
    ),

    Rule(
        lhs=NETERMINALS[NeterminalName.L_LIST],
        rhs=[
            [
                TERMINALS[TerminalName.LPAREN],
                NETERMINALS[NeterminalName.FORM_LIST],
                TERMINALS[TerminalName.RPAREN],
            ],
        ]
    ),

    Rule(
        lhs=NETERMINALS[NeterminalName.P_LIST],
        rhs=[
            [
                TERMINALS[TerminalName.LBRACKET],
                NETERMINALS[NeterminalName.FORM_LIST],
                TERMINALS[TerminalName.RBRACKET],
            ],
        ]
    ),

    Rule(
        lhs=NETERMINALS[NeterminalName.S_LIST],
        rhs=[
            [
                TERMINALS[TerminalName.LANGLE],
                NETERMINALS[NeterminalName.FORM_LIST],
                TERMINALS[TerminalName.RANGLE],
            ],
        ]
    ),
]


PLANNER_GRAMMAR = Grammar(
    terminals=list(TERMINALS.values()),
    non_terminals=list(NETERMINALS.values()),
    rules=RULES,
    start=NETERMINALS[NeterminalName.PROGRAM],
)
