from pathlib import Path

from .graph import Graph
from ..grammar import PLANNER_GRAMMAR, Grammar


class PlannerGraphLoader:
    GRAPH_DIR = Path(__file__).parent
    GRAPH_PROTO = GRAPH_DIR / "planner_graph.pb.txt"
    GRAPH_VIS   = GRAPH_DIR / "planner_lgraph"
    
    @staticmethod
    def save(grammar: Grammar) -> None:
        graph = Graph.from_grammar(grammar)
        graph.dump(PlannerGraphLoader.GRAPH_PROTO)
        graph.visualize(filename=PlannerGraphLoader.GRAPH_VIS, view=False)
    
    @staticmethod
    def load() -> Graph:
        if not PlannerGraphLoader.GRAPH_PROTO.exists():
            PlannerGraphLoader.save(PLANNER_GRAMMAR)

        return Graph.load(PlannerGraphLoader.GRAPH_PROTO)


PLANNER_GRAPH = PlannerGraphLoader.load()