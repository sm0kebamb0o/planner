from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from google.protobuf import text_format

from ..common import Neterminal, Terminal
from .proto import grammar_pb2


EPSILON = Terminal("eps", id="Terminal_eps")


@dataclass
class Rule:
    lhs: Neterminal
    rhs: list[list[Terminal | Neterminal]]


@dataclass
class Grammar:
    terminals     : list[Terminal]
    non_terminals : list[Neterminal]
    rules         : list[Rule]
    start         : Neterminal

    @classmethod
    def parse(
        cls,
        text: str,
        terminals: list[Terminal],
        non_terminals: list[Neterminal],
        start: Neterminal | None = None,
    ) -> "Grammar":
        """Parse a CFG from text."""
        if EPSILON in terminals:
            raise ValueError(f"{EPSILON.value!r} must not appear in the terminals set")
        if EPSILON in non_terminals:
            raise ValueError(f"{EPSILON.value!r} must not appear in the non-terminals set")

        _terminal_map:    dict[str, Terminal]   = {t.value:  t  for t in terminals}
        _nonterminal_map: dict[str, Neterminal] = {nt.value: nt for nt in non_terminals}

        def is_terminal(sym: str) -> bool:
            return sym in _terminal_map or sym == EPSILON.value

        def is_neterminal(sym: str) -> bool:
            return sym in _nonterminal_map

        rules_map:   dict[str, Rule] = {}
        rules_order: list[Rule]      = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if "->" in line:
                lhs_part, rhs_part = line.split("->", 1)
            else:
                raise ValueError(f"No arrow found in line: {line!r}")

            lhs_str = lhs_part.strip()
            if not lhs_str:
                raise ValueError(f"Empty LHS in line: {line!r}")

            if not is_neterminal(lhs_str):
                raise ValueError(f"LHS symbol {lhs_str!r} is not a non-terminal")

            lhs = _nonterminal_map[lhs_str]

            if not start:
                start = lhs

            if lhs_str not in rules_map:
                rule = Rule(lhs=lhs, rhs=[])
                rules_map[lhs_str] = rule
                rules_order.append(rule)

            rule = rules_map[lhs_str]

            for alternative in rhs_part.split("|"):
                tokens = alternative.split()
                if not tokens or (len(tokens) == 1 and tokens[0] == EPSILON.value):
                    alt: list[Terminal | Neterminal] = [EPSILON]
                else:
                    alt = []
                    for tok in tokens:
                        if is_terminal(tok):
                            alt.append(_terminal_map.get(tok, EPSILON))
                        elif is_neterminal(tok):
                            alt.append(_nonterminal_map[tok])
                        else:
                            raise ValueError(f"Symbol {tok!r} is neither a terminal nor a non-terminal")
                rule.rhs.append(alt)

        if not start:
            raise ValueError("Start symbol is not provided")

        if start not in non_terminals:
            raise ValueError(
                f"Start symbol {start.value!r} is not in the non-terminals set"
            )

        return cls(
            terminals=terminals,
            non_terminals=non_terminals,
            rules=rules_order,
            start=start,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def dump(self, file_path: str | Path) -> None:
        proto = grammar_pb2.Grammar()
        proto.start_id = self.start.id

        for t in self.terminals:
            pt = proto.terminals.add()
            pt.id = t.id
            pt.value = t.value

        for nt in self.non_terminals:
            pnt = proto.neterminals.add()
            pnt.id = nt.id
            pnt.value = nt.value

        for rule in self.rules:
            pr = proto.rules.add()
            pr.lhs_id = rule.lhs.id
            for alt in rule.rhs:
                pa = pr.rhs.add()
                for sym in alt:
                    ps = pa.symbols.add()
                    if isinstance(sym, Terminal):
                        ps.terminal_id = sym.id
                    else:
                        ps.neterminal_id = sym.id

        Path(file_path).write_text(text_format.MessageToString(proto))

    @classmethod
    def load(cls, file_path: str | Path) -> "Grammar":
        proto = grammar_pb2.Grammar()
        text_format.Parse(Path(file_path).read_text(), proto)

        id_to_terminal:   dict[str, Terminal]   = {}
        id_to_neterminal: dict[str, Neterminal] = {}

        for pt in proto.terminals:
            t = Terminal(pt.value, id=pt.id)
            id_to_terminal[t.id] = t

        id_to_terminal[EPSILON.id] = EPSILON

        for pnt in proto.neterminals:
            nt = Neterminal(pnt.value, id=pnt.id)
            id_to_neterminal[nt.id] = nt

        rules: list[Rule] = []
        for pr in proto.rules:
            lhs = id_to_neterminal[pr.lhs_id]
            rhs: list[list[Terminal | Neterminal]] = []
            for pa in pr.rhs:
                alt: list[Terminal | Neterminal] = []
                for ps in pa.symbols:
                    which = ps.WhichOneof("kind")
                    if which == "terminal_id":
                        alt.append(id_to_terminal[ps.terminal_id])
                    else:
                        alt.append(id_to_neterminal[ps.neterminal_id])
                rhs.append(alt)
            rules.append(Rule(lhs=lhs, rhs=rhs))

        return cls(
            terminals=[t for t in id_to_terminal.values() if t != EPSILON],
            non_terminals=list(id_to_neterminal.values()),
            rules=rules,
            start=id_to_neterminal[proto.start_id],
        )
