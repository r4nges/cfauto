import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta

import pytest

from cfauto.core import clock


class RelogioFixo:
    def __init__(self, inicio: datetime) -> None:
        self.atual = inicio

    def agora(self) -> datetime:
        return self.atual

    def avancar(self, **delta: float) -> None:
        self.atual += timedelta(**delta)

    def definir(self, quando: datetime) -> None:
        self.atual = quando


@pytest.fixture
def relogio():
    r = RelogioFixo(datetime(2026, 9, 23, 10, 0, 0))
    clock.definir(r.agora)
    yield r
    clock.resetar()
