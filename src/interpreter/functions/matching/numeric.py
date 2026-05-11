from __future__ import annotations

import operator as _op


def register(matchers: dict, interp) -> None:
    def _num_cmp(op):
        def fn(args, expr, interp):
            if not args or not isinstance(expr, (int, float)):
                return False
            n = interp.eval_form(args[0])
            if not isinstance(n, (int, float)):
                return False
            return op(expr, n)
        return fn

    matchers["LT"] = _num_cmp(_op.lt)
    matchers["LE"] = _num_cmp(_op.le)
    matchers["GT"] = _num_cmp(_op.gt)
    matchers["GE"] = _num_cmp(_op.ge)
