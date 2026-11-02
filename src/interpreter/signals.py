from src.interpreter.values import Value


class PlannerFailure(BaseException):
    """Сигнал неуспеха в режиме возвратов"""
    def __init__(self, message: "Value | None" = None,
                 target: str | None = None) -> None:
        self.message: "Value" = message  # type: ignore[assignment]
        self.target = target
