from enum import StrEnum

from src.interpreter.values import Value


class ProgStepStatus(StrEnum):
    OK        = "ok"
    GO        = "go"
    RETURN    = "return"
    EXHAUSTED = "exhausted"


class GoSignal(BaseException):
    def __init__(self, label: str) -> None:
        self.label = label


class ReturnSignal(BaseException):
    def __init__(self, value: Value) -> None:
        self.value = value


class PlannerFailure(BaseException):
    """Сигнал неуспеха в режиме возвратов"""
    def __init__(self, message: "Value | None" = None,
                 target: str | None = None) -> None:
        self.message: "Value" = message  # type: ignore[assignment]
        self.target = target