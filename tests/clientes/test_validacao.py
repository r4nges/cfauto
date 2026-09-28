from decimal import Decimal

import pytest

from cfauto.clientes.validacao import (
    cpf_valido,
    formatar_celular,
    formatar_cpf,
    formatar_saldo,
    normalizar_celular,
    normalizar_cpf,
    normalizar_email,
    normalizar_nome,
    so_digitos,
)
from cfauto.core.errors import ValorInvalido


def test_so_digitos():
    assert so_digitos("(11) 98765-4321") == "11987654321"
    assert so_digitos("abc") == ""


def test_normalizar_nome_colapsa_espacos():
    assert normalizar_nome("  Ana   Maria  Souza ") == "Ana Maria Souza"


@pytest.mark.parametrize("nome", ["", "   ", "Ana"])
def test_nome_exige_duas_palavras(nome):
    with pytest.raises(ValorInvalido, match="nome e sobrenome"):
        normalizar_nome(nome)


def test_nome_longo_demais():
    with pytest.raises(ValorInvalido, match="120"):
        normalizar_nome("Ana " + "x" * 120)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("(11) 98765-4321", "11987654321"),
        ("11 98765 4321", "11987654321"),
        ("+55 (11) 98765-4321", "11987654321"),
        ("5511987654321", "11987654321"),
        ("(11) 3456-7890", "1134567890"),
        ("+55 11 3456-7890", "1134567890"),
        ("55 99123-4567", "55991234567"),  # DDD 55 (RS), não é código do país
    ],
)
def test_normalizar_celular_aceita_formatos(texto, esperado):
    assert normalizar_celular(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "mensagem"),
    [
        ("", "obrigatório"),
        ("() -", "obrigatório"),
        ("98765-4321", "DDD \\+ número"),
        ("123", "DDD \\+ número"),
        ("(01) 98765-4321", "DDD inválido"),
    ],
)
def test_celular_invalido(texto, mensagem):
    with pytest.raises(ValorInvalido, match=mensagem):
        normalizar_celular(texto)


@pytest.mark.parametrize("cpf", ["52998224725", "11144477735"])
def test_cpf_valido(cpf):
    assert cpf_valido(cpf)


@pytest.mark.parametrize("cpf", ["52998224726", "11111111111", "1234567890", "", "5299822472a"])
def test_cpf_invalido(cpf):
    assert not cpf_valido(cpf)


def test_normalizar_cpf():
    assert normalizar_cpf("529.982.247-25") == "52998224725"
    assert normalizar_cpf("") is None
    assert normalizar_cpf("   ") is None
    assert normalizar_cpf("..-") is None
    for invalido in ("529.982.247-26", "111.111.111-11", "abc"):
        with pytest.raises(ValorInvalido, match="CPF inválido"):
            normalizar_cpf(invalido)


def test_normalizar_email():
    assert normalizar_email(" ana@loja.com.br ") == "ana@loja.com.br"
    assert normalizar_email("  ") is None
    for invalido in ("ana.com", "ana@loja", "ana @loja.com", "a@b.c" + "x" * 120):
        with pytest.raises(ValorInvalido, match="E-mail inválido"):
            normalizar_email(invalido)


def test_formatadores():
    assert formatar_celular("11987654321") == "(11) 98765-4321"
    assert formatar_celular("1134567890") == "(11) 3456-7890"
    assert formatar_cpf("52998224725") == "529.982.247-25"
    assert formatar_cpf(None) == ""
    assert formatar_saldo(Decimal("120.5")) == "R$ 120,50"
    assert formatar_saldo(Decimal("0")) == "R$ 0,00"
    assert formatar_saldo(Decimal("-30")) == "Crédito a favor R$ 30,00"
