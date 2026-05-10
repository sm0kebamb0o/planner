from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto

from google.protobuf import text_format
from graphviz import Digraph

from ..common.models import Terminal, Neterminal
from ..common.auto_id import AutoIdMeta
from ..grammar import Grammar, EPSILON

from .proto import graph_pb2


@dataclass
class Vertex(metaclass=AutoIdMeta):
    name : str
    id   : str = field(init=False)


@dataclass
class BracketsPair(metaclass=AutoIdMeta):
    id : str = field(init=False)


@dataclass
class Bracket:
    class Type(Enum):
        OPEN = auto()
        CLOSE = auto()

    type : Type
    id   : str

    def __str__(self) -> str:
        return f"{'(' if self.type == self.Type.OPEN else ')'}_{self.id}"


@dataclass
class Edge(metaclass=AutoIdMeta):
    vertex1 : Vertex
    vertex2 : Vertex
    value   : Terminal | Bracket
    id      : str = field(init=False)


@dataclass
class Graph:
    initial   : Vertex
    _vertices : dict[str, Vertex] = field(default_factory=dict)
    _edges    : dict[str, Edge]   = field(default_factory=dict)
    final     : list[Vertex]      = field(default_factory=list)
    terminals : list[Terminal]    = field(default_factory=list)
    brackets  : list[Bracket]     = field(default_factory=list)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    @property
    def vertices(self) -> list[Vertex]:
        return list(self._vertices.values())

    @property
    def edges(self) -> list[Edge]:
        return list(self._edges.values())

    def add_vertex(self, vertex: Vertex) -> "Graph":
        self._vertices[vertex.id] = vertex
        return self

    def add_edge(self, edge: Edge) -> "Graph":
        self._edges[edge.id] = edge
        return self

    def adjacency_by_name(self) -> dict[str, list["Edge"]]:
        result: dict[str, list[Edge]] = defaultdict(list)
        for edge in self.edges:
            result[edge.vertex1.name].append(edge)
        return dict(result)

    @property
    def start_name(self) -> str:
        return self.initial.name

    @property
    def final_names(self) -> frozenset[str]:
        return frozenset(v.name for v in self.final)

    @property
    def start_id(self) -> str:
        return self.initial.id

    @property
    def final_ids(self) -> frozenset[str]:
        return frozenset(v.id for v in self.final)

    def vertex_by_id(self, vertex_id: str) -> "Vertex":
        return self._vertices[vertex_id]
    
    def vertex_by_name(self, vertex_name: str) -> "Vertex":
        for v in self._vertices.values():
            if v.name == vertex_name:
                return v
        raise KeyError(f"Нет вершины {vertex_name!r} в графе")

    def is_final(self, vertex_id: str) -> bool:
        return vertex_id in self.final_ids

    def nt_start_id(self, nt_name: str) -> str:
        target = f"{nt_name}_beg"
        for v in self._vertices.values():
            if v.name == target:
                return v.id
        raise KeyError(f"Нет вершины {target!r} в графе")

    def nt_end_id(self, nt_name: str) -> str:
        target = f"{nt_name}_end"
        for v in self._vertices.values():
            if v.name == target:
                return v.id
        raise KeyError(f"Нет вершины {target!r} в графе")

    def adjacency_by_id(self) -> dict[str, list["Edge"]]:
        result: dict[str, list[Edge]] = defaultdict(list)
        for edge in self.edges:
            result[edge.vertex1.id].append(edge)
        return dict(result)

    def transition_table(
        self,
        vertex_name: str,
        adj: dict[str, list["Edge"]],
    ) -> dict[str, list["Edge"]]:
        groups: dict[str, list[Edge]] = {}
        for edge in adj.get(vertex_name, []):
            if isinstance(edge.value, Terminal):
                key = "eps" if edge.value.value == "eps" else f"terminal:{edge.value.value}"
            else:
                key = "open" if edge.value.type == Bracket.Type.OPEN else "close"
            groups.setdefault(key, []).append(edge)
        return groups

    @staticmethod
    def from_grammar(grammar: Grammar) -> "Graph":
        """Build a context-free L-graph from a CFG"""

        def vertex_name_beg(nt: str) -> str:
            return f"{nt}_beg"

        def vertex_name_end(nt: str) -> str:
            return f"{nt}_end"

        def vertex_name_mid(nt: str, rule_idx: int, pos: int) -> str:
            return f"{nt}_{rule_idx}_{pos}"

        used_vertices: dict[str, tuple[Vertex, Vertex]] = {}
        def get_beg_end_vertices(nonterminal: Neterminal) -> tuple[Vertex, Vertex]:
            if nonterminal.id not in used_vertices:
                beg_vertex = Vertex(vertex_name_beg(nonterminal.value))
                end_vertex = Vertex(vertex_name_end(nonterminal.value))
                used_vertices[nonterminal.id] = (beg_vertex, end_vertex)
            return used_vertices[nonterminal.id]

        initial_vertex, finish_vertex = get_beg_end_vertices(grammar.start)
        graph = Graph(initial=initial_vertex, final=[finish_vertex])

        alt_idx = 0
        for rule in grammar.rules:
            lhs = rule.lhs
            v_beg, v_end = get_beg_end_vertices(lhs)

            for rhs in rule.rhs:
                n = len(rhs)
                seq_vertices: list[Vertex] = [v_beg]
                for j in range(1, n):
                    seq_vertices.append(Vertex(vertex_name_mid(lhs, alt_idx, j)))
                seq_vertices.append(v_end)

                for i, sym in enumerate(rhs):
                    v_left = seq_vertices[i]
                    v_right = seq_vertices[i + 1]

                    graph.add_vertex(v_left)
                    graph.add_vertex(v_right)

                    if sym in grammar.non_terminals:
                        brackets_pair = BracketsPair()
                        open_bracket = Bracket(type=Bracket.Type.OPEN, id=brackets_pair.id)
                        close_bracket = Bracket(type=Bracket.Type.CLOSE, id=brackets_pair.id)
                        v_sym_beg, v_sym_end = get_beg_end_vertices(sym)
                        graph.add_edge(Edge(vertex1=v_left, vertex2=v_sym_beg, value=open_bracket))
                        graph.add_edge(Edge(vertex1=v_sym_end, vertex2=v_right, value=close_bracket))
                        graph.brackets.append(open_bracket)
                        graph.brackets.append(close_bracket)
                    elif sym in grammar.terminals or sym == EPSILON:
                        graph.add_edge(Edge(vertex1=v_left, vertex2=v_right, value=sym))
                    else:
                        raise ValueError(f"Symbol {sym!r} is not a terminal or non-terminal")

                alt_idx += 1

        graph.terminals = list(grammar.terminals)
        if any(isinstance(e.value, Terminal) and e.value == EPSILON for e in graph.edges):
            if EPSILON not in graph.terminals:
                graph.terminals.append(EPSILON)
        return graph

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def dump(self, file_path: str) -> None:
        proto = graph_pb2.Graph()
        proto.initial = self.initial.id

        for f in self.final:
            proto.final.append(f.id)

        for v in self.vertices:
            pv = proto.vertices.add()
            pv.id = v.id
            pv.name = v.name

        for t in self.terminals:
            pt = proto.terminals.add()
            pt.id = t.id
            pt.value = t.value

        for b in self.brackets:
            pb_msg = proto.brackets.add()
            pb_msg.id = b.id
            pb_msg.type = b.type.name

        for e in self.edges:
            pe = proto.edges.add()
            pe.id = e.id
            pe.vertex1_id = e.vertex1.id
            pe.vertex2_id = e.vertex2.id
            if isinstance(e.value, Terminal):
                pe.terminal_id = e.value.id
            elif isinstance(e.value, Bracket):
                pe.bracket_id = e.value.id

        with open(file_path, "w") as f:
            f.write(text_format.MessageToString(proto))

    @classmethod
    def load(cls, file_path: str) -> "Graph":
        proto = graph_pb2.Graph()
        with open(file_path, "r") as f:
            text_format.Parse(f.read(), proto)

        id_to_vertex:    dict[str, Vertex]   = {}
        id_to_terminal:  dict[str, Terminal] = {}
        open_brackets:   dict[str, Bracket]  = {}
        close_brackets:  dict[str, Bracket]  = {}

        for pv in proto.vertices:
            v = Vertex(pv.name, id=pv.id)
            id_to_vertex[v.id] = v

        for pt in proto.terminals:
            t = Terminal(pt.value, id=pt.id)
            id_to_terminal[t.id] = t

        for pb in proto.brackets:
            b = Bracket(type=Bracket.Type[pb.type], id=pb.id)
            if b.type == Bracket.Type.OPEN:
                open_brackets[b.id] = b
            else:
                close_brackets[b.id] = b

        initial_vertex = id_to_vertex[proto.initial]
        g = cls(initial=initial_vertex)

        for v in id_to_vertex.values():
            g._vertices[v.id] = v

        g.terminals = list(id_to_terminal.values())
        g.brackets  = list(open_brackets.values()) + list(close_brackets.values())
        g.final     = [id_to_vertex[fid] for fid in proto.final if fid in id_to_vertex]

        for pe in proto.edges:
            which = pe.WhichOneof("value")
            if which == "terminal_id":
                value: Terminal | Bracket = id_to_terminal[pe.terminal_id]
            else:
                # Open brackets lead to *_beg vertices; all others are close brackets
                dest_name = id_to_vertex[pe.vertex2_id].name
                bracket_pool = open_brackets if dest_name.endswith("_beg") else close_brackets
                value = bracket_pool[pe.bracket_id]
            e = Edge(
                vertex1=id_to_vertex[pe.vertex1_id],
                vertex2=id_to_vertex[pe.vertex2_id],
                value=value,
                id=pe.id,
            )
            g._edges[e.id] = e

        return g

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def visualize(self, filename: str = "lgraph", view: bool = True) -> None:
        dot = Digraph(name="lgraph", graph_attr={"rankdir": "LR", "fontsize": "12"})

        initial_name = self.initial.name if self.initial else None
        final_names = {v.name for v in self.final}

        for v in self._vertices.values():
            if v.name == initial_name and v.name in final_names:
                dot.node(v.name, shape="doublecircle", style="filled", fillcolor="orange")
            elif v.name == initial_name:
                dot.node(v.name, shape="circle", style="filled", fillcolor="lightgreen")
            elif v.name in final_names:
                dot.node(v.name, shape="doublecircle", style="filled", fillcolor="salmon")
            else:
                dot.node(v.name, shape="circle", style="filled", fillcolor="lightblue")

        bracket_id_to_num: dict[str, int] = {}
        for i, b in enumerate(self.brackets, start=1):
            if b.id not in bracket_id_to_num:
                bracket_id_to_num[b.id] = i

        edge_labels: dict[tuple[str, str], list[str]] = {}
        for e in self.edges:
            u, w = e.vertex1.name, e.vertex2.name
            if isinstance(e.value, Terminal):
                label = e.value.value
            else:
                b = e.value
                num = bracket_id_to_num[b.id]
                prefix = "(" if b.type == Bracket.Type.OPEN else ")"
                label = f"{prefix}_{num}"
            edge_labels.setdefault((u, w), []).append(label)

        for (u, w), labels in edge_labels.items():
            dot.edge(u, w, label=", ".join(labels))

        dot.render(filename, format="png", view=view, cleanup=True)
