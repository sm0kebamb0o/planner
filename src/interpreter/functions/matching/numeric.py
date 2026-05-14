import operator as _op


def register(matchers: dict, interp) -> None:
    def _num_cmp(op):
        def fn(args, expr):
            if not args or not isinstance(expr, (int, float)):
                return False
            n = interp.eval_form(args[0])
            if not isinstance(n, (int, float)):
                return False
            return op(expr, n)
        return fn

    matchers["LT"] = lambda args, expr: _num_cmp(_op.lt)(args, expr)
    matchers["LE"] = lambda args, expr: _num_cmp(_op.le)(args, expr)
    matchers["GT"] = lambda args, expr: _num_cmp(_op.gt)(args, expr)
    matchers["GE"] = lambda args, expr: _num_cmp(_op.ge)(args, expr)
