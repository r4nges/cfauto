from datetime import date, datetime

import pytest

from cfauto.core.dates import para_data, para_datahora
from cfauto.core.errors import DataInvalida


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("17/09/2026", date(2026, 9, 17)),
        ("2026-09-17", date(2026, 9, 17)),
        ("17/09/26", date(2026, 9, 17)),
        ("17-09-2026", date(2026, 9, 17)),
        ("17/09/2026 14:30", date(2026, 9, 17)),
        (date(2026, 9, 17), date(2026, 9, 17)),
        (datetime(2026, 9, 17, 8, 0), date(2026, 9, 17)),
    ],
)
def test_para_data(entrada, esperado):
    assert para_data(entrada) == esperado


@pytest.mark.parametrize("entrada", ["31/02/2026", "", "amanhã", "2026/13/01", 20260917])
def test_para_data_invalida(entrada):
    with pytest.raises(DataInvalida):
        para_data(entrada)


def test_para_datahora():
    assert para_datahora("17/09/2026 14:30:05") == datetime(2026, 9, 17, 14, 30, 5)
    assert para_datahora("2026-09-17T14:30:05") == datetime(2026, 9, 17, 14, 30, 5)
    assert para_datahora("17/09/2026") == datetime(2026, 9, 17, 0, 0)
    assert para_datahora(date(2026, 9, 17)) == datetime(2026, 9, 17)


def test_iso_com_fuso_vira_hora_local():
    assert para_datahora("2026-09-20T10:15:00-03:00") == datetime(2026, 9, 20, 10, 15)
    assert para_datahora("2026-09-20T10:15:00Z") == datetime(2026, 9, 20, 10, 15)
    assert para_data("2026-09-20T23:59:59-03:00") == date(2026, 9, 20)
