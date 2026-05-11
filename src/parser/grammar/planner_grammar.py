from enum import StrEnum
from pathlib import Path

from src.lexer import TT
from ..common.models import Terminal, Neterminal

from .grammar import Grammar, Rule, EPSILON


TerminalName = TT


class NeterminalName(StrEnum):
    FORM_LIST = "FormList"
    FORM      = "Form"
    ATOM      = "Atom"
    VAR_REF   = "VarRef"
    L_LIST    = "LList"
    P_LIST    = "PList"
    S_LIST    = "SList"


def _build_grammar() -> Grammar:
    terminals: dict[TerminalName, Terminal] = {
        t: Terminal(t.name)
        for t in TerminalName
    }
    neterminals: dict[NeterminalName, Neterminal] = {
        nt: Neterminal(nt) for nt in NeterminalName
    }

    rules: list[Rule] = [
        Rule(
            lhs=neterminals[NeterminalName.FORM_LIST],
            rhs=[
                [
                    neterminals[NeterminalName.FORM],
                    neterminals[NeterminalName.FORM_LIST],
                ],
                [EPSILON],
            ]
        ),

        Rule(
            lhs=neterminals[NeterminalName.FORM],
            rhs=[
                [neterminals[NeterminalName.ATOM]],
                [neterminals[NeterminalName.VAR_REF]],
                [neterminals[NeterminalName.L_LIST]],
                [neterminals[NeterminalName.P_LIST]],
                [neterminals[NeterminalName.S_LIST]],
            ]
        ),

        Rule(
            lhs=neterminals[NeterminalName.ATOM],
            rhs=[
                [terminals[TerminalName.IDENT]],
                [terminals[TerminalName.INT]],
                [terminals[TerminalName.FLOAT]],
                [terminals[TerminalName.SCALE]],
            ]
        ),

        Rule(
            lhs=neterminals[NeterminalName.VAR_REF],
            rhs=[
                [terminals[TerminalName.DOT], terminals[TerminalName.IDENT]],
                [terminals[TerminalName.STAR], terminals[TerminalName.IDENT]],
                [terminals[TerminalName.COLON], terminals[TerminalName.IDENT]],
                [terminals[TerminalName.BANG_DOT], terminals[TerminalName.IDENT]],
                [terminals[TerminalName.BANG_STAR], terminals[TerminalName.IDENT]],
                [terminals[TerminalName.BANG_COLON], terminals[TerminalName.IDENT]],
            ]
        ),

        Rule(
            lhs=neterminals[NeterminalName.L_LIST],
            rhs=[
                [
                    terminals[TerminalName.LPAREN],
                    neterminals[NeterminalName.FORM_LIST],
                    terminals[TerminalName.RPAREN],
                ],
            ]
        ),

        Rule(
            lhs=neterminals[NeterminalName.P_LIST],
            rhs=[
                [
                    terminals[TerminalName.LBRACKET],
                    neterminals[NeterminalName.FORM_LIST],
                    terminals[TerminalName.RBRACKET],
                ],
            ]
        ),

        Rule(
            lhs=neterminals[NeterminalName.S_LIST],
            rhs=[
                [
                    terminals[TerminalName.LANGLE],
                    neterminals[NeterminalName.FORM_LIST],
                    terminals[TerminalName.RANGLE],
                ],
            ]
        ),
    ]

    return Grammar(
        terminals=list(terminals.values()),
        non_terminals=list(neterminals.values()),
        rules=rules,
        start=neterminals[NeterminalName.FORM],
    )


class PlannerGrammarLoader:
    GRAMMAR_DIR = Path(__file__).parent
    GRAMMAR_PROTO = GRAMMAR_DIR / "planner_grammar.pb.txt"

    def save():
        grammar = _build_grammar()
        grammar.dump(PlannerGrammarLoader.GRAMMAR_PROTO)

    @staticmethod
    def load() -> Grammar:
        if not PlannerGrammarLoader.GRAMMAR_PROTO.exists():
            PlannerGrammarLoader.save()
        return Grammar.load(PlannerGrammarLoader.GRAMMAR_PROTO)


PLANNER_GRAMMAR = PlannerGrammarLoader.load()
