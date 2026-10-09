from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from cfauto.core.errors import ValorInvalido
from cfauto.ui.comum import (
    aplicar_mascara_data,
    criar_tabela,
    formatar_data_digitada,
    ler_decimal,
    ler_decimal_opcional,
)


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


@pytest.mark.parametrize(
    ("digitado", "esperado"),
    [
        ("", ""),
        ("1", "1"),
        ("15", "15"),
        ("150", "15/0"),
        ("1503", "15/03"),
        ("15031", "15/03/1"),
        ("15031990", "15/03/1990"),
        ("150319901234", "15/03/1990"),  # passa de 8 dígitos: o resto é cortado
        ("15/03/1990", "15/03/1990"),
        ("15/", "15"),  # sem barra sobrando: o Backspace não trava
        ("15/03/90", "15/03/90"),
        ("1990-03-15", "1990-03-15"),  # ISO colada fica como está
    ],
)
def test_formatar_data_digitada(digitado, esperado):
    assert formatar_data_digitada(digitado) == esperado


def _campo_data(qtbot):
    campo = QLineEdit()
    qtbot.addWidget(campo)
    aplicar_mascara_data(campo)
    return campo


def test_mascara_poe_as_barras_ao_digitar(qtbot):
    campo = _campo_data(qtbot)
    qtbot.keyClicks(campo, "15031990")
    assert campo.text() == "15/03/1990"


def test_mascara_aceita_as_barras_digitadas(qtbot):
    campo = _campo_data(qtbot)
    qtbot.keyClicks(campo, "15/03/1990")
    assert campo.text() == "15/03/1990"


def test_mascara_deixa_apagar_com_backspace(qtbot):
    campo = _campo_data(qtbot)
    qtbot.keyClicks(campo, "15031")
    assert campo.text() == "15/03/1"
    for esperado in ("15/03", "15/0", "15", "1", ""):
        qtbot.keyClick(campo, Qt.Key.Key_Backspace)
        assert campo.text() == esperado


def test_mascara_mantem_o_cursor_ao_editar_no_meio(qtbot):
    campo = _campo_data(qtbot)
    campo.setText("15/03")
    campo.setCursorPosition(0)
    qtbot.keyClicks(campo, "29")
    assert campo.text() == "29/15/03"
    assert campo.cursorPosition() == 2


def test_criar_tabela_liga_a_zebra(qapp):
    assert criar_tabela(["A", "B"]).alternatingRowColors() is True
