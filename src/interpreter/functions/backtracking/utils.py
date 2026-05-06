def _close_forks_since(interp, depth: int) -> None:
    while len(interp._fork_stack) > depth:
        gen = interp._fork_stack.pop()
        try:
            gen.close()
        except Exception:
            pass


def _tracked_gen(gen, interp):
    interp._fork_stack.append(gen)
    try:
        yield from gen
    finally:
        try:
            interp._fork_stack.remove(gen)
        except ValueError:
            pass
