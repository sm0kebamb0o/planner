from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from ..errors import ParseError
from ..grammar import NeterminalName, TerminalName
from .nodes import (
    FormNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)
from src.lexer import TT


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


ASTItem = Union[TokItem, FormNode, list]


def assemble_node(nt_name: str, items: list[ASTItem]) -> ASTItem | None:
    if nt_name == NeterminalName.ATOM:
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

    if nt_name == NeterminalName.VAR_REF:
        assert len(items) == 2 and all(isinstance(x, TokItem) for x in items)
        prefix_tok = items[0]
        name_tok   = items[1]
        if prefix_tok.type not in _PREFIX_MAP:
            raise ParseError(f"VarRef: неизвестный префикс {prefix_tok.type!r}")
        mode, segmented = _PREFIX_MAP[prefix_tok.type]
        return VarRefNode(mode=mode, name=name_tok.text, segmented=segmented)

    if nt_name == NeterminalName.FORM:
        assert len(items) == 1 and isinstance(items[0], FormNode)
        return items[0]

    if nt_name == NeterminalName.FORM_LIST:
        result: list[FormNode] = []
        for item in items:
            if isinstance(item, FormNode):
                result.append(item)
            elif isinstance(item, list):
                result.extend(item)
        return result

    if nt_name == NeterminalName.L_LIST:
        elements: list[FormNode] = []
        for item in items:
            if isinstance(item, list):
                elements = item
                break
        return LListNode(elements=elements)

    if nt_name == NeterminalName.P_LIST:
        pb = next((x for x in items if isinstance(x, list)), [])
        if not pb:
            return CallNode(head=IdentNode(""), args=[], segmented=False)
        head_node = pb[0]
        if not isinstance(head_node, FormNode):
            raise ParseError(f"PList: недопустимая голова {head_node!r}")
        return CallNode(head=head_node, args=list(pb[1:]), segmented=False)

    if nt_name == NeterminalName.S_LIST:
        sb = next((x for x in items if isinstance(x, list)), [])
        if not sb:
            return CallNode(head=IdentNode(""), args=[], segmented=True)
        head_node = sb[0]
        if not isinstance(head_node, FormNode):
            raise ParseError(f"SList: недопустимая голова {head_node!r}")
        return CallNode(head=head_node, args=list(sb[1:]), segmented=True)

    raise ParseError(f"assemble_node: неизвестный нетерминал {nt_name!r}")
