from __future__ import annotations

from src.parser.ast.nodes import (
    FormNode, IdentNode, IntNode, FloatNode, ScaleNode,
    VarRefNode, VarMode, LListNode, CallNode,
)
from src.interpreter.values import Value, PlannerList, ScaleValue, BracketKind, NIL
from src.interpreter.errors import PlannerRuntimeError


_VAR_PREFIX = {
    (VarMode.READ,   False): ".",
    (VarMode.ASSIGN, False): "*",
    (VarMode.CONST,  False): ":",
    (VarMode.READ,   True):  "!.",
    (VarMode.ASSIGN, True):  "!*",
    (VarMode.CONST,  True):  "!:",
}


def ast_to_value(node: FormNode) -> Value:
    if isinstance(node, IdentNode):
        return node.name
    if isinstance(node, IntNode):
        return node.value
    if isinstance(node, FloatNode):
        return node.value
    if isinstance(node, ScaleNode):
        return ScaleValue(bits=node.bits, source=node.source)
    if isinstance(node, VarRefNode):
        return PlannerList(
            elements=[_VAR_PREFIX[(node.mode, node.segmented)] + node.name],
            kind=BracketKind.ROUND,
        )
    if isinstance(node, LListNode):
        return PlannerList(
            elements=[ast_to_value(e) for e in node.elements],
            kind=BracketKind.ROUND,
        )
    if isinstance(node, CallNode):
        kind = BracketKind.ANGLE if node.segmented else BracketKind.SQUARE
        elems = [ast_to_value(node.head)] + [ast_to_value(a) for a in node.args]
        return PlannerList(elements=elems, kind=kind)
    raise PlannerRuntimeError(f"ast_to_value: неизвестный тип {type(node)}")


def value_to_form(val: Value) -> FormNode:
    if isinstance(val, str):
        return IdentNode(name=val)
    if isinstance(val, int):
        return IntNode(value=val)
    if isinstance(val, float):
        return FloatNode(value=val)
    if isinstance(val, ScaleValue):
        return ScaleNode(bits=val.bits, source=val.source)
    if isinstance(val, PlannerList):
        if val.kind == BracketKind.SQUARE and val.elements:
            head_node = value_to_form(val.elements[0])
            arg_nodes = [value_to_form(e) for e in val.elements[1:]]
            return CallNode(head=head_node, args=arg_nodes, segmented=False)
        if val.kind == BracketKind.ANGLE and val.elements:
            head_node = value_to_form(val.elements[0])
            arg_nodes = [value_to_form(e) for e in val.elements[1:]]
            return CallNode(head=head_node, args=arg_nodes, segmented=True)
        return LListNode(elements=[value_to_form(e) for e in val.elements])
    raise PlannerRuntimeError(
        f"value_to_form: нельзя конвертировать {type(val)} в форму"
    )


def value_to_pattern(val: Value) -> FormNode:
    """Преобразует маркеры переменных QUOTE, сохраняя обычные значения EVAL."""
    if not isinstance(val, PlannerList):
        return value_to_form(val)
    if (val.kind == BracketKind.ROUND and len(val.elements) == 1
            and isinstance(val.elements[0], str)):
        marker = val.elements[0]
        for (mode, segmented), prefix in sorted(
                _VAR_PREFIX.items(), key=lambda pair: -len(pair[1])):
            if marker.startswith(prefix) and len(marker) > len(prefix):
                return VarRefNode(mode, marker[len(prefix):], segmented)
    if val.kind in (BracketKind.SQUARE, BracketKind.ANGLE):
        if not val.elements or val.elements == [""]:
            return CallNode(IdentNode(""), [], val.kind == BracketKind.ANGLE)
        return CallNode(value_to_pattern(val.elements[0]),
                        [value_to_pattern(e) for e in val.elements[1:]],
                        val.kind == BracketKind.ANGLE)
    return LListNode([value_to_pattern(e) for e in val.elements])


def repr_form(node: FormNode) -> str:
    if isinstance(node, IdentNode):
        return node.name
    if isinstance(node, IntNode):
        return str(node.value)
    if isinstance(node, FloatNode):
        return str(node.value)
    if isinstance(node, ScaleNode):
        return f"*{node.source}"
    if isinstance(node, VarRefNode):
        return _VAR_PREFIX[(node.mode, node.segmented)] + node.name
    if isinstance(node, LListNode):
        inner = " ".join(repr_form(e) for e in node.elements)
        return f"({inner})"
    if isinstance(node, CallNode):
        lb = "<" if node.segmented else "["
        rb = ">" if node.segmented else "]"
        parts = [repr_form(node.head)] + [repr_form(a) for a in node.args]
        return f"{lb}{' '.join(parts)}{rb}"
    return repr(node)


def repr_value(val: Value, float_digits: int = 6) -> str:
    if val is NIL or (isinstance(val, PlannerList) and not val.elements):
        return "()"
    if isinstance(val, str):
        return val
    if isinstance(val, bool):
        return "T" if val else "()"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return f"{val:.{float_digits}f}"
    if isinstance(val, ScaleValue):
        return f"*{val.source}"
    if isinstance(val, PlannerList):
        inner = " ".join(repr_value(e, float_digits) for e in val.elements)
        brackets = {
            BracketKind.ROUND:  ("(", ")"),
            BracketKind.SQUARE: ("[", "]"),
            BracketKind.ANGLE:  ("<", ">"),
        }
        l, r = brackets[val.kind]
        return f"{l}{inner}{r}"
    return repr(val)
