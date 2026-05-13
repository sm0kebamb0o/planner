def _close_forks_since(interp, depth: int) -> None:
    # Удаляем F-точки с конца стека
    while len(interp._fork_stack) > depth:
        gen = interp._fork_stack.pop()
        try:
            gen.close()
        except Exception:
            pass


def _tracked_gen(gen, interp):
    # Добпавляем F-точку
    interp._fork_stack.append(gen)
    try:
        yield from gen
    finally:
        interp._fork_stack.remove(gen)
