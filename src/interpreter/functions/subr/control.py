from src.interpreter.control_flow import ControlRequest, EvalStream, GoRequest, ReturnRequest
from src.interpreter.errors import PlannerRuntimeError
from src.interpreter.values import NIL
from src.interpreter.functions.utils import check_arity


def _emit_control(request: ControlRequest, interp) -> EvalStream:
    # Временно снимаем вложенные кадры на время выполнения продолжения владельца.
    # Сравниваем объекты: содержимое разных кадров может совпадать.
    index = next(i for i, frame in enumerate(interp.env._frames)
                 if frame is request.target)
    suspended = interp.env._frames[index + 1:]
    del interp.env._frames[index + 1:]
    try:
        yield request
    finally:
        interp.env._frames.extend(suspended)


def go(args: list, interp) -> EvalStream:
    check_arity("GO", args, 1)
    label = args[0]
    if not isinstance(label, str):
        raise PlannerRuntimeError("GO: аргумент должен быть идентификатором")
    for frame in reversed(interp.env._frames):
        if label in frame.labels:
            yield from _emit_control(GoRequest(frame, frame.labels[label]), interp)
            return
        if frame.is_function:
            raise PlannerRuntimeError(
                f"GO: метка '{label}' не определена (выход за границу LAMBDA)"
            )
    raise PlannerRuntimeError(f"GO: метка '{label}' не определена")


def return_(args: list, interp) -> EvalStream:
    check_arity("RETURN", args, 1)
    for frame in reversed(interp.env._frames):
        if frame.is_prog:
            yield from _emit_control(ReturnRequest(frame, args[0]), interp)
            return
    raise PlannerRuntimeError("RETURN: нет объемлющего PROG или DO")


def exit_(args: list, interp) -> EvalStream:
    value = args[0] if args else NIL
    yield from return_([value], interp)


def register(interp) -> None:
    interp._bt_subrs["GO"] = lambda args: go(args, interp)
    interp._bt_subrs["RETURN"] = lambda args: return_(args, interp)
    interp._bt_subrs["EXIT"] = lambda args: exit_(args, interp)
