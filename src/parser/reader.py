from __future__ import annotations

from src.parser.grammar import EPSILON

from .ast import FormNode, ProgramNode
from .ast.assembler import TokItem, ASTItem, assemble_node
from .errors import ParseError
from .graph import Graph, Edge, Bracket, PLANNER_GRAPH
from src.lexer import Token
from .common.auto_id import Id
from .common.models import Terminal


class PlannerReader:
    def __init__(self) -> None:
        self.graph: Graph = PLANNER_GRAPH

        self._vertex_name: dict[Id, str] = {
            v.id: v.name for v in self.graph.vertices
        }

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
        tokens = group
        tok_pos = 0

        current: Id = self.graph.start_id
        b_stack: list[tuple[str, str]] = []
        ast_stack: list[list[ASTItem]] = [[]]

        while True:
            if self.graph.is_final(current) and not b_stack:
                # Разобрали форму полностью
                break

            if tok_pos < len(tokens):
                tt: str = tokens[tok_pos].type.name
            else:
                tt = "EOF"

            edge = self._find_edge(current, tt, b_stack)

            if edge is None:
                vname = self._vertex_name.get(current, current)
                if tok_pos < len(tokens):
                    tok = tokens[tok_pos]
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
                    tok = tokens[tok_pos]
                    tok_pos += 1
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
                    node = assemble_node(nt_name, items)
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
        vertex_id: Id,
        token_type: str,
        b_stack: list[tuple[str, str]],
    ) -> Edge | None:
        """Из всех рёбер текущей вершины выбирается первое подходящее:
        1. Терминальное ребро с пометкой == token_type
        2. Открывающая скобка к NT_beg, если token_type \in FIRST(NT)
        3. Закрывающая скобка, если b_stack[-1][0] == edge.value.id
        4. eps-ребро (запасной вариант; покрывает пустой FormList)
        """
        edges = self.graph.get_adjacent_edges(vertex_id)
        eps_edge:      Edge | None = None
        nullable_edge: Edge | None = None

        for edge in edges:
            edge_value = edge.value

            if isinstance(edge_value, Terminal):
                if edge_value == EPSILON:
                    eps_edge = edge
                elif edge_value.value == token_type:
                    return edge

            elif isinstance(edge_value, Bracket):
                if edge_value.type == Bracket.Type.OPEN:
                    nt_beg_name = self._vertex_name.get(edge.vertex2.id, "")
                    nt_name = (
                        nt_beg_name[: -len("_beg")]
                        if nt_beg_name.endswith("_beg")
                        else nt_beg_name
                    )

                    if token_type in self.graph.first.get(nt_name, frozenset()):
                        return edge

                    if nt_name in self.graph.nullable:
                        nullable_edge = edge

                elif edge_value.type == Bracket.Type.CLOSE:
                    if b_stack and b_stack[-1][0] == edge_value.id:
                        return edge

                else:
                    raise ParseError(f"Неизвестный тип скобки: {edge_value.type!r}")

        return nullable_edge if nullable_edge else eps_edge
