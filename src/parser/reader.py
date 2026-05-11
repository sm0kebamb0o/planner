from __future__ import annotations
from collections import namedtuple

from src.parser.common.auto_id import Id
from src.parser.grammar import EPSILON

from .ast import FormNode, ProgramNode
from .ast.stack import TokItem, ASTStack
from .errors import ParseError
from .graph import Graph, Edge, Bracket, PLANNER_GRAPH, Vertex
from src.lexer import TT, Token
from .common.models import Terminal, Neterminal


class PlannerReader:
    def __init__(self) -> None:
        self.graph: Graph = PLANNER_GRAPH

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
        tokens = iter(group)
        def seek_token() -> Token | None:
            next_token = next(tokens, None)
            if not next_token:
                return namedtuple(
                    "FinalToken",
                    ["type", "value", "line", "col"]
                )("Final", None, -1, -1)
            return next_token

        current_token = seek_token()

        current_vertex = self.graph.start_vertex
        b_stack: list[tuple[Id, Neterminal]] = []
        ast = ASTStack()

        # Тут нельзя итерироваться только по токенам,
        # потому что нужно дойти до финальной вершины
        while True:
            # TODO: нужно предусмотреть механизм
            # от зацикливания и долгого блуждания
            if self.graph.is_final(current_vertex) and not b_stack:
                # Смогли разобрать форму полностью
                break

            edge = self._find_edge(current_vertex, current_token.type, b_stack)

            if edge is None:
                raise ParseError(
                    f"Нет подходящего перехода из вершины {current_vertex.name!r} "
                    f"при токене {current_token.type!r} ({current_token.line}:{current_token.col})"
                )

            ev = edge.value

            if isinstance(ev, Terminal):
                if ev != EPSILON:
                    ast.append(TokItem(current_token.type, current_token.value))
                    current_token = seek_token()

                current_vertex = edge.vertex2

            elif isinstance(ev, Bracket):
                if ev.type == Bracket.Type.OPEN:
                    b_stack.append((ev.id, ev.neterminal))
                    ast.push()
                    current_vertex = edge.vertex2
                elif ev.type == Bracket.Type.CLOSE:
                    if not b_stack:
                        raise ParseError(
                            f"Несогласованная закрывающая скобка в вершине {current_vertex.name!r}"
                        )
                    open_id, neterminal = b_stack.pop()
                    if open_id != ev.id:
                        raise ParseError(
                            f"Несоответствие скобок: ожидался {open_id!r}, "
                            f"получен {ev.id!r}"
                        )
                    ast.close_frame(neterminal)
                    current_vertex = edge.vertex2
                else:
                    raise ParseError(f"Неизвестный тип скобки: {ev.type!r}")

        return ast.result()

    def _find_edge(
        self,
        vertex: Vertex,
        token_type: TT | None,
        b_stack: list[tuple[Id, Neterminal]],
    ) -> Edge | None:
        """Из всех рёбер текущей вершины выбирается первое подходящее:
        1. Терминальное ребро с пометкой == token_type
        2. Открывающая скобка к NT_beg, если token_type in FIRST(NT)
        3. Закрывающая скобка, если b_stack[-1][0] == edge.value.id
        4. eps-ребро (запасной вариант; покрывает пустой FormList)
        """
        edges = self.graph.get_adjacent_edges(vertex)
        eps_edge:      Edge | None = None
        nullable_edge: Edge | None = None

        for edge in edges:
            edge_value = edge.value

            if isinstance(edge_value, Terminal):
                if edge_value == EPSILON:
                    eps_edge = edge
                elif token_type and edge_value.value == token_type.name:
                    return edge

            elif isinstance(edge_value, Bracket):
                if edge_value.type == Bracket.Type.OPEN:
                    nt_beg_id = edge.vertex2.id

                    if token_type and token_type.name in self.graph.first.get(nt_beg_id, frozenset()):
                        return edge

                    if nt_beg_id in self.graph.nullable:
                        nullable_edge = edge

                elif edge_value.type == Bracket.Type.CLOSE:
                    if b_stack and b_stack[-1][0] == edge_value.id:
                        return edge

                else:
                    raise ParseError(f"Неизвестный тип скобки: {edge_value.type!r}")

        # Не нашли подходящего ребра ни по типу токена, ни по скобке
        
        # Переходим по скобке, которая выводит eps, актуально для FormList
        if nullable_edge:
            return nullable_edge
        
        # Пробуем перейти по eps-ребру, актуально для FormList
        if eps_edge:
            return eps_edge
        
        return None
