from decimal import Decimal

import pytest

from cfauto.core.errors import ValorInvalido
from cfauto.core.money import arredondar, formatar_brl, para_decimal


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("R$ 1.234,56", Decimal("1234.56")),
        ("10.5", Decimal("10.5")),
        ("10,5", Decimal("10.5")),
        ("1.234", Decimal("1234")),
        ("1.234.567", Decimal("1234567")),
        ("-3,20", Decimal("-3.20")),
        ("-R$ 3,20", Decimal("-3.20")),
        ("  7 ", Decimal("7")),
        (7, Decimal("7")),
        (0.1, Decimal("0.1")),
        (Decimal("2.50"), Decimal("2.50")),
    ],
)
def test_para_decimal(entrada, esperado):
    assert para_decimal(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "abc", "1,2,3", "NaN", "Infinity", True])
def test_para_decimal_invalido(entrada):
    with pytest.raises(ValorInvalido):
        para_decimal(entrada)


def test_arredondar_meio_para_cima():
    assert arredondar(Decimal("2.675")) == Decimal("2.68")
    assert arredondar(Decimal("2.674")) == Decimal("2.67")
    assert arredondar(Decimal("-2.675")) == Decimal("-2.68")


def test_formatar_brl():
    assert formatar_brl(Decimal("1234567.8")) == "R$ 1.234.567,80"
    assert formatar_brl(Decimal("0")) == "R$ 0,00"
    assert formatar_brl(Decimal("-3.2")) == "-R$ 3,20"
