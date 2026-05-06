from .values import Value


class _GoSignal(BaseException):
    """Сигнал перехода по метке ([GO label]).

    Наследован от BaseException (не Exception) чтобы не перехватывался
    левыми 'except Exception:' внутри функций.
    """
    def __init__(self, label: str) -> None:
        self.label = label


class _ReturnSignal(BaseException):
    def __init__(self, value: Value) -> None:
        self.value = value


class PlannerRuntimeError(Exception):
    """Ошибка времени выполнения программы на Плэннере."""


class PlannerFailure(BaseException):
    """Сигнал неуспеха в режиме возвратов.

    Наследован от BaseException чтобы не перехватывался обычными
    'except Exception:' внутри интерпретатора.

    Атрибуты:
        message: сообщение, связанное с неуспехом (значение [MESS]).
        target:  имя именованной развилки для [FAIL e name];
                 None означает «ближайшая развилка».
    """
    def __init__(self, message: "Value | None" = None,
                 target: str | None = None) -> None:
        self.message: "Value" = message  # type: ignore[assignment]
        self.target = target