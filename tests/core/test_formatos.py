from decimal import Decimal

import pytest

from cfauto.core.money import (
    arredondar_custo,
    arredondar_qtd,
    formatar_numero,
    formatar_pct,
    formatar_qtd,
)
from cfauto.core.texto import normalizar_texto


def test_arredondamentos():
    assert str(arredondar_qtd(Decimal("2.4995"))) == "2.500"
    assert str(arredondar_custo(Decimal("6.12345"))) == "6.1235"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (Decimal("1.500"), "1,5"),
        (Decimal("1234"), "1.234"),
        (Decimal("-2.25"), "-2,25"),
        (Decimal("0"), "0"),
        (Decimal("0.0004"), "0"),
    ],
)
def test_formatar_qtd(valor, esperado):
    assert formatar_qtd(valor) == esperado


def test_formatar_pct():
    assert formatar_pct(Decimal("0.125")) == "12,5%"
    assert formatar_pct(Decimal("0.5")) == "50,0%"
    assert formatar_pct(Decimal("-0.25")) == "-25,0%"


@pytest.mark.parametrize(
    ("valor", "casas", "esperado"),
    [
        (Decimal("1234.5"), 2, "1234,50"),
        (Decimal("0.0350"), 2, "0,035"),
        (Decimal("78.0000"), 2, "78,00"),
        (Decimal("12.000"), 0, "12"),
        (Decimal("2.500"), 0, "2,5"),
    ],
)
def test_formatar_numero(valor, casas, esperado):
    assert formatar_numero(valor, casas) == esperado


def test_normalizar_texto():
    assert normalizar_texto("  Açúcar   CRISTAL ") == "acucar cristal"
    assert normalizar_texto("Pão-de-Ló") == "pao-de-lo"
