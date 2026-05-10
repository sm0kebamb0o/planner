from dataclasses import dataclass

from ..common import Neterminal, Terminal


EPSILON = Terminal("eps", id="Terminal_eps")


@dataclass
class Rule:
    lhs: Neterminal
    rhs: list[list[Terminal | Neterminal]]


@dataclass
class Grammar:
    terminals:     list[Terminal]
    non_terminals: list[Neterminal]
    rules:         list[Rule]
    start:         Neterminal

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
