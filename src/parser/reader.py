from __future__ import annotations

from dataclasses import dataclass

from .ast_nodes import (
    FormNode, ProgramNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)
from .grammar import NeterminalName, TerminalName
from .graph import Graph, Edge, Bracket, PLANNER_GRAPH
from src.lexer import Token, TT
from .common.models import Terminal


# Префикс-токен → (VarMode, segmented)
_PREFIX_MAP: dict[TT, tuple[VarMode, bool]] = {
    TT.DOT:        (VarMode.READ,   False),
    TT.STAR:       (VarMode.ASSIGN, False),
    TT.COLON:      (VarMode.CONST,  False),
    TT.BANG_DOT:   (VarMode.READ,   True),
    TT.BANG_STAR:  (VarMode.ASSIGN, True),
    TT.BANG_COLON: (VarMode.CONST,  True),
}


class ParseError(Exception):
    """Синтаксическая ошибка при разборе."""


@dataclass
class TokItem:
    """Потреблённый терминальный токен, хранимый в АСД-фрейме."""
    type: TT
    text: str


ASTItem = TokItem | FormNode | list


class PlannerReader:
    def __init__(self) -> None:
        self.graph: Graph = PLANNER_GRAPH

        self._vertex_name: dict[str, str] = {
            v.id: v.name for v in self.graph.vertices
        }
        self._adj: dict[str, list[Edge]] = self.graph.adjacency_by_id()
        self._first: dict[str, frozenset[str]] = self._build_first_sets()
        self._nullable: frozenset[str] = self._build_nullable()

        self._form_start_id: str = self.graph.vertex_by_name("Form_beg").id
        self._form_end_id: str = self.graph.vertex_by_name("Form_end").id

        self._tokens:  list[Token] = []
        self._tok_pos: int = 0

    def _build_nullable(self) -> frozenset[str]:
        nullable: set[str] = set()
        for vertex_id, edges in self._adj.items():
            vname = self._vertex_name.get(vertex_id, "")
            if not vname.endswith("_beg"):
                continue
            nt_name = vname[: -len("_beg")]
            for edge in edges:
                if (
                    isinstance(edge.value, Terminal)
                    and edge.value.value == "eps"
                ):
                    nullable.add(nt_name)
                    break
        return frozenset(nullable)

    def _build_first_sets(self) -> dict[str, frozenset[str]]:
        first: dict[str, frozenset[str]] = {}

        def compute(beg_vertex_id: str, seen: frozenset[str]) -> frozenset[str]:
            if beg_vertex_id in seen:
                return frozenset()
            seen = seen | {beg_vertex_id}
            result: set[str] = set()

            for edge in self._adj.get(beg_vertex_id, []):
                if isinstance(edge.value, Terminal):
                    if edge.value.value != "eps":
                        result.add(edge.value.value)
                elif (
                    isinstance(edge.value, Bracket)
                    and edge.value.type == Bracket.Type.OPEN
                ):
                    sub_first = compute(edge.vertex2.id, seen)
                    result.update(sub_first)

            return frozenset(result)

        for vertex_id in self._adj:
            vname = self._vertex_name.get(vertex_id, "")
            if vname.endswith("_beg"):
                nt_name = vname[: -len("_beg")]
                first[nt_name] = compute(vertex_id, frozenset())

        return first

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def read(self, token_groups: list[list[Token]]) -> ProgramNode:
        forms: list[FormNode] = []
        for group in token_groups:
            form = self._parse_form(group)
            forms.append(form)
        return ProgramNode(forms=forms)

    # ------------------------------------------------------------------
    # Inner methods
    # ------------------------------------------------------------------

    def _parse_form(self, group: list[Token]) -> FormNode:
        self._tokens  = group
        self._tok_pos = 0

        current: str = self._form_start_id
        b_stack: list[tuple[str, str]] = []
        ast_stack: list[list[ASTItem]] = [[]]

        while True:
            if current == self._form_end_id and not b_stack:
                break

            if self._tok_pos < len(self._tokens):
                tt: str = self._tokens[self._tok_pos].type.name
            else:
                tt = "EOF"

            edge = self._find_edge(current, tt, b_stack)

            if edge is None:
                vname = self._vertex_name.get(current, current)
                if self._tok_pos < len(self._tokens):
                    tok = self._tokens[self._tok_pos]
                    raise ParseError(
                        f"Нет подходящего перехода из вершины {vname!r} "
                        f"при токене {tt!r} ({tok.line}:{tok.col})"
                    )
                raise ParseError(
                    f"Нет подходящего перехода из вершины {vname!r} "
                    f"при токене {tt!r}"
                )

            ev = edge.value

            if isinstance(ev, Terminal):
                if ev.value == "eps":
                    current = edge.vertex2.id
                else:
                    tok = self._advance_tok()
                    ast_stack[-1].append(TokItem(tok.type, tok.value))
                    current = edge.vertex2.id

            elif isinstance(ev, Bracket):
                if ev.type == Bracket.Type.OPEN:
                    nt_vertex_id = edge.vertex2.id
                    nt_name = self._vertex_name.get(nt_vertex_id, "")
                    if nt_name.endswith("_beg"):
                        nt_name = nt_name[: -len("_beg")]
                    b_stack.append((ev.id, nt_name))
                    ast_stack.append([])
                    current = nt_vertex_id
                elif ev.type == Bracket.Type.CLOSE:
                    if not b_stack:
                        vname = self._vertex_name.get(current, current)
                        raise ParseError(
                            f"Несогласованная закрывающая скобка в вершине {vname!r}"
                        )
                    open_id, nt_name = b_stack.pop()
                    if open_id != ev.id:
                        raise ParseError(
                            f"Несоответствие скобок: ожидался {open_id!r}, "
                            f"получен {ev.id!r}"
                        )
                    items = ast_stack.pop()
                    node = self._assemble_node(nt_name, items)
                    if node is not None:
                        ast_stack[-1].append(node)
                    current = edge.vertex2.id
                else:
                    raise ValueError(f"Неизвестный тип скобки: {ev.type!r}")

        for item in ast_stack[0]:
            # TODO: почему я тут смотрю только на первый фрейм?
            if isinstance(item, FormNode):
                return item
        raise ParseError(f"Form: не удалось извлечь узел из фрейма {ast_stack[0]!r}")

    def _find_edge(
        self,
        vertex_id: str,
        token_type: str,
        b_stack: list[tuple[str, str]],
    ) -> Edge | None:
        """Из всех рёбер текущей вершины выбирается первое подходящее:
        1. Терминальное ребро с пометкой == tt
        2. Открывающая скобка к NT_beg, если tt \in FIRST(NT)
        3. Закрывающая скобка, если b_stack[-1][0] == edge.value.id
        4. eps-ребро (запасной вариант; покрывает пустой FormList)
        """
        edges = self._adj.get(vertex_id, [])
        eps_edge:      Edge | None = None
        nullable_edge: Edge | None = None

        for edge in edges:
            ev = edge.value

            if isinstance(ev, Terminal):
                if ev.value == "eps":
                    eps_edge = edge
                elif ev.value == token_type:
                    return edge

            elif isinstance(ev, Bracket):
                if ev.type == Bracket.Type.OPEN:
                    nt_beg_name = self._vertex_name.get(edge.vertex2.id, "")
                    nt_name = (
                        nt_beg_name[: -len("_beg")]
                        if nt_beg_name.endswith("_beg")
                        else nt_beg_name
                    )

                    if token_type in self._first.get(nt_name, frozenset()):
                        return edge

                    if nt_name in self._nullable:
                        nullable_edge = edge

                elif ev.type == Bracket.Type.CLOSE:
                    if b_stack and b_stack[-1][0] == ev.id:
                        return edge
                
                else:
                    raise ValueError(f"Неизвестный тип скобки: {ev.type!r}")

        return nullable_edge if nullable_edge is not None else eps_edge

    def _assemble_node(
        self,
        nt_name: str,
        items: list[ASTItem],
    ) -> ASTItem | None:
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

        if nt_name == NeterminalName.PROGRAM:
            return None

        raise ParseError(f"_assemble_node: неизвестный нетерминал {nt_name!r}")

    def _peek_tok(self) -> Token:
        return self._tokens[self._tok_pos]

    def _advance_tok(self) -> Token:
        tok = self._tokens[self._tok_pos]
        self._tok_pos += 1
        return tok
