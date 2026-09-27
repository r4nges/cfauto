"""Única fonte de data/hora atual do sistema. Substituível em testes."""

from collections.abc import Callable
from datetime import date, datetime

_fonte: Callable[[], datetime] = datetime.now


def agora() -> datetime:
    return _fonte()


def hoje() -> date:
    return _fonte().date()


def definir(fonte: Callable[[], datetime]) -> None:
    global _fonte
    _fonte = fonte


def resetar() -> None:
    definir(datetime.now)
