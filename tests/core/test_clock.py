from datetime import date, datetime

from cfauto.core import clock


def test_relogio_fixo(relogio):
    assert clock.agora() == datetime(2026, 9, 23, 10, 0, 0)
    assert clock.hoje() == date(2026, 9, 23)
    relogio.avancar(days=1)
    assert clock.hoje() == date(2026, 9, 24)


def test_resetar_volta_ao_relogio_real():
    clock.definir(lambda: datetime(2000, 1, 1))
    clock.resetar()
    assert clock.hoje().year >= 2026
