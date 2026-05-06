from src.interpreter.models.values import NIL, Value
from src.interpreter.models.signals import PlannerRuntimeError, _GoSignal, _ReturnSignal
from src.parser.ast_nodes import LListNode, IdentNode
from .utils import _close_forks_since
from .perm_strg_temp import cleanup_perm, cleanup_strg, cleanup_temp


def _make_xprog(cleanup_fn):
    def _fsubr_xprog(raw_args: list, interp) -> Value:
        if not raw_args:
            raise PlannerRuntimeError("PPROG/SPROG/TPROG: нужен список переменных")

        var_list_node = raw_args[0]
        body_nodes    = raw_args[1:]

        if not isinstance(var_list_node, LListNode):
            raise PlannerRuntimeError("PPROG/SPROG/TPROG: первый аргумент — список переменных")

        declared_names = []
        init_bindings  = {}
        for decl in var_list_node.elements:
            if isinstance(decl, IdentNode):
                declared_names.append(decl.name)
            elif isinstance(decl, LListNode) and len(decl.elements) == 2:
                name_node = decl.elements[0]
                if not isinstance(name_node, IdentNode):
                    raise PlannerRuntimeError("PPROG/SPROG/TPROG: неверное объявление переменной")
                declared_names.append(name_node.name)
                init_bindings[name_node.name] = interp.eval_form(decl.elements[1])

        labels = {}
        for i, node in enumerate(body_nodes):
            if isinstance(node, IdentNode):
                labels[node.name] = i

        depth = len(interp._fork_stack)
        mark  = interp._trail.mark()

        interp.env.push_frame(
            declared=declared_names,
            bindings=init_bindings,
            labels=labels,
            is_prog=True,
        )
        try:
            last_val: Value = NIL
            i = 0
            while i < len(body_nodes):
                node = body_nodes[i]
                if isinstance(node, IdentNode) and node.name in labels:
                    i += 1
                    continue
                try:
                    last_val = interp.eval_form(node)
                except _GoSignal as go:
                    if go.label in labels:
                        i = labels[go.label]
                        continue
                    raise
                i += 1
            cleanup_fn(interp, depth, mark)
            return last_val
        except _ReturnSignal as ret:
            cleanup_fn(interp, depth, mark)
            return ret.value
        finally:
            interp.env.pop_frame()

    return _fsubr_xprog


_pprog_impl = _make_xprog(cleanup_perm)
_sprog_impl = _make_xprog(cleanup_strg)
_tprog_impl = _make_xprog(cleanup_temp)


def register(interp) -> None:
    interp._fsubrs["PPROG"] = lambda raw: _pprog_impl(raw, interp)
    interp._fsubrs["SPROG"] = lambda raw: _sprog_impl(raw, interp)
    interp._fsubrs["TPROG"] = lambda raw: _tprog_impl(raw, interp)
