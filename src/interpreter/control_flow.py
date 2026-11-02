from dataclasses import dataclass
from typing import Generator

from src.interpreter.env import Frame
from src.interpreter.signals import PlannerFailure
from src.interpreter.values import Value


@dataclass(frozen=True)
class ControlRequest:
    target: Frame


@dataclass(frozen=True)
class GoRequest(ControlRequest):
    index: int


@dataclass(frozen=True)
class ReturnRequest(ControlRequest):
    value: Value


EvalItem = Value | ControlRequest
EvalStream = Generator[EvalItem, None, None]


class ControlExhausted(PlannerFailure):
    """После передачи управления значения исчерпаны; запасной результат не создаётся.

    Возникает только при исчерпании возобновлённого потока и не используется
    для передачи управления через активные генераторы.
    """
