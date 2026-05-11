from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from src.lexer import TT
from src.parser.ast.nodes import (
    FormNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)
from src.parser.common.models import Neterminal
from src.parser.errors import ParseError
from src.parser.grammar import NeterminalName, TerminalName


# Префикс-токен → (VarMode, segmented)
_PREFIX_MAP: dict[TT, tuple[VarMode, bool]] = {
    TT.DOT:        (VarMode.READ,   False),
    TT.STAR:       (VarMode.ASSIGN, False),
    TT.COLON:      (VarMode.CONST,  False),
    TT.BANG_DOT:   (VarMode.READ,   True),
    TT.BANG_STAR:  (VarMode.ASSIGN, True),
    TT.BANG_COLON: (VarMode.CONST,  True),
}


@dataclass
class TokItem:
    """Потреблённый терминальный токен, хранимый в АСД-фрейме."""
    type: TT
    text: str


@dataclass
class FormList:
    """Промежуточный список форм, возвращаемый FORM_LIST."""
    items: list[FormNode]


ASTItem = Union[TokItem, FormNode, FormList]


class ASTStack:
    def __init__(self) -> None:
        self._frames: list[list[ASTItem]] = [[]]

    def append(self, item: ASTItem) -> None:
        self._frames[-1].append(item)

    def push(self) -> None:
        self._frames.append([])

    def pop(self) -> list[ASTItem]:
        return self._frames.pop()

    def close_frame(self, nt: Neterminal) -> None:
        node = self._assemble_node(nt, self.pop())
        if node is not None:
            self.append(node)

    def result(self) -> FormNode:
        assert len(self._frames) == 1, "В стеке должен был остаться только один фрейм"
        frame = self._frames[0]
        assert len(frame) == 1 and isinstance(frame[0], FormNode), \
            f"Фрейм должен содержать ровно одну форму, получено: {frame!r}"
        return frame[0]

    def _assemble_node(self, nt: Neterminal, items: list[ASTItem]) -> ASTItem | None:
        if nt == NeterminalName.ATOM:
            assert len(items) == 1 and isinstance(items[0], TokItem)
            tok = items[0]
            if tok.type == TerminalName.IDENT:
                return IdentNode(name=tok.text)
            if tok.type == TerminalName.INT:
                return IntNode(value=int(tok.text))
            if tok.type == TerminalName.FLOAT:
                return FloatNode(value=float(tok.text))
            if tok.type == TerminalName.SCALE:
                octal = tok.text[1:]
                return ScaleNode(bits=int(octal, 8), source=octal)
            raise ParseError(f"Atom: неизвестный тип токена {tok.type!r}")

        if nt == NeterminalName.VAR_REF:
            assert len(items) == 2 and all(isinstance(x, TokItem) for x in items)
            prefix_tok = items[0]
            name_tok   = items[1]
            if prefix_tok.type not in _PREFIX_MAP:
                raise ParseError(f"VarRef: неизвестный префикс {prefix_tok.type!r}")
            mode, segmented = _PREFIX_MAP[prefix_tok.type]
            return VarRefNode(mode=mode, name=name_tok.text, segmented=segmented)

        if nt == NeterminalName.FORM:
            assert len(items) == 1 and isinstance(items[0], FormNode)
            return items[0]

        if nt == NeterminalName.FORM_LIST:
            result: list[FormNode] = []
            for item in items:
                if isinstance(item, FormNode):
                    result.append(item)
                elif isinstance(item, FormList):
                    result.extend(item.items)
                else:
                    raise ParseError(f"FormList: неизвестный тип элемента {type(item)!r}")
            return FormList(result)

        if nt == NeterminalName.L_LIST:
            assert (
                len(items) == 3
                and isinstance(items[0], TokItem) and items[0].type == TT.LPAREN
                and isinstance(items[1], FormList)
                and isinstance(items[2], TokItem) and items[2].type == TT.RPAREN
            )
            return LListNode(elements=items[1].items)

        if nt == NeterminalName.P_LIST:
            assert (
                len(items) == 3
                and isinstance(items[0], TokItem) and items[0].type == TT.LBRACKET
                and isinstance(items[1], FormList)
                and isinstance(items[2], TokItem) and items[2].type == TT.RBRACKET
            )
            pb = items[1].items
            if not pb:
                # Под сопоставители []
                return CallNode(head=IdentNode(""), args=[], segmented=False)
            return CallNode(head=pb[0], args=pb[1:], segmented=False)

        if nt == NeterminalName.S_LIST:
            assert (
                len(items) == 3
                and isinstance(items[0], TokItem) and items[0].type == TT.LANGLE
                and isinstance(items[1], FormList)
                and isinstance(items[2], TokItem) and items[2].type == TT.RANGLE
            )
            sb = items[1].items
            if not sb:
                # Под сопоставители <>
                return CallNode(head=IdentNode(""), args=[], segmented=True)
            return CallNode(head=sb[0], args=sb[1:], segmented=True)

        raise ParseError(f"_assemble_node: неизвестный нетерминал {nt!r}")
