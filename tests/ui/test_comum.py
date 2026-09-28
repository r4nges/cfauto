from decimal import Decimal

import pytest

from cfauto.core.errors import ValorInvalido
from cfauto.ui.comum import ler_decimal, ler_decimal_opcional


def test_ler_decimal_aceita_formato_brasileiro():
    assert ler_decimal("1.234,56", "Preço") == Decimal("1234.56")


@pytest.mark.parametrize("entrada", ["1e3", "1E20", "-2e-3", "1.5e10"])
def test_ler_decimal_rejeita_notacao_cientifica(entrada):
    with pytest.raises(ValorInvalido, match="notação científica"):
        ler_decimal(entrada, "Preço")


def test_ler_decimal_rejeita_valor_absurdamente_grande():
    with pytest.raises(ValorInvalido, match="grande demais"):
        ler_decimal("99999999999999", "Preço")  # 14 dígitos, nunca estoura como OverflowError


def test_ler_decimal_aceita_valor_no_teto():
    assert ler_decimal("9999999999", "Preço") == Decimal("9999999999")


def test_ler_decimal_mensagem_traz_o_rotulo():
    with pytest.raises(ValorInvalido, match="Custo:"):
        ler_decimal("abc", "Custo")


def test_ler_decimal_opcional_vazio_e_none():
    assert ler_decimal_opcional("   ", "Preço") is None


def test_ler_decimal_opcional_propaga_erro():
    with pytest.raises(ValorInvalido, match="notação científica"):
        ler_decimal_opcional("1e3", "Preço")
