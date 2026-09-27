from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.core.errors import PermissaoNegada, ValorInvalido
from cfauto.core.models import AuditLog
from cfauto.gestao.bens import (
    atualizar_bem,
    baixar_bem,
    criar_bem,
    listar_bens,
    reativar_bem,
    total_bens_ativos,
)
from cfauto.gestao.models import TipoBem
from cfauto.gestao.schemas import DadosBem


def _bem(sessao, ator, descricao="Balcão", valor="1500", tipo=TipoBem.MOVEL, **campos):
    return criar_bem(
        sessao, ator, DadosBem(descricao=descricao, tipo=tipo, valor=Decimal(valor), **campos)
    )


def test_criar_bem_com_codigo_e_data_de_hoje(sessao, admin):
    bem = _bem(sessao, admin)
    assert (bem.codigo, bem.data_cadastro, bem.valor, bem.ativo) == (
        "BEM-001",
        date(2026, 9, 23),
        Decimal("1500"),
        True,
    )
    assert _bem(sessao, admin, "Software", tipo=TipoBem.INTANGIVEL).codigo == "BEM-002"


def test_data_informada_e_respeitada(sessao, admin):
    assert _bem(sessao, admin, data_cadastro=date(2025, 1, 10)).data_cadastro == date(2025, 1, 10)


@pytest.mark.parametrize(
    ("descricao", "valor", "mensagem"),
    [("  ", "10", "Descrição"), ("Mesa", "0", "maior que zero"), ("Mesa", "-5", "maior que zero")],
)
def test_validacoes(sessao, admin, descricao, valor, mensagem):
    with pytest.raises(ValorInvalido, match=mensagem):
        _bem(sessao, admin, descricao, valor)


def test_total_so_de_bens_ativos(sessao, admin):
    balcao = _bem(sessao, admin, valor="1000.50")
    _bem(sessao, admin, "Freezer", valor="499.50")
    assert total_bens_ativos(sessao, admin) == Decimal("1500.00")
    baixar_bem(sessao, admin, balcao.id)
    assert total_bens_ativos(sessao, admin) == Decimal("499.50")
    assert [b.codigo for b in listar_bens(sessao, admin)] == ["BEM-002"]
    assert [b.codigo for b in listar_bens(sessao, admin, incluir_baixados=True)] == [
        "BEM-001",
        "BEM-002",
    ]
    with pytest.raises(ValorInvalido, match="baixado"):
        baixar_bem(sessao, admin, balcao.id)
    reativar_bem(sessao, admin, balcao.id)
    assert total_bens_ativos(sessao, admin) == Decimal("1500.00")


def test_total_sem_bens_e_zero(sessao, admin):
    assert total_bens_ativos(sessao, admin) == Decimal("0")


def test_atualizar_mantem_data_e_audita(sessao, admin, relogio):
    bem = _bem(sessao, admin)
    relogio.avancar(days=10)
    atualizar_bem(
        sessao,
        admin,
        bem.id,
        DadosBem(descricao="Balcão inox", tipo=TipoBem.MOVEL, valor=Decimal("1800")),
    )
    assert (bem.descricao, bem.valor, bem.data_cadastro) == (
        "Balcão inox",
        Decimal("1800"),
        date(2026, 9, 23),
    )
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "bem_fisico", AuditLog.acao == "alterar")
    ).one()
    assert registro.antes["valor"] == "1500.00"
    assert registro.depois["valor"] == "1800.00"


def test_so_admin(sessao, estoquista):
    with pytest.raises(PermissaoNegada):
        _bem(sessao, estoquista)
    with pytest.raises(PermissaoNegada):
        total_bens_ativos(sessao, estoquista)
