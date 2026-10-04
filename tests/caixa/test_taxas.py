from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.caixa.models import FormaPagamento
from cfauto.caixa.schemas import TaxaForma
from cfauto.caixa.taxas import atualizar_taxa, listar_taxas, taxa_da_forma
from cfauto.core.errors import PermissaoNegada, ValorInvalido
from cfauto.core.models import AuditLog

D = Decimal


def test_operador_do_pdv_lista_as_taxas_padrao_em_ordem(sessao, operador):
    assert listar_taxas(sessao, operador) == [
        TaxaForma(FormaPagamento.DINHEIRO, D("0.00"), 0, False),
        TaxaForma(FormaPagamento.PIX, D("0.00"), 0, False),
        TaxaForma(FormaPagamento.DEBITO, D("1.50"), 7, False),
        TaxaForma(FormaPagamento.CREDITO, D("3.50"), 7, False),
    ]


def test_sem_pdv_nao_lista(sessao, estoquista):
    with pytest.raises(PermissaoNegada):
        listar_taxas(sessao, estoquista)


def test_taxa_da_forma(sessao):
    assert taxa_da_forma(sessao, FormaPagamento.CREDITO) == TaxaForma(
        FormaPagamento.CREDITO, D("3.50"), 7, False
    )
    assert taxa_da_forma(sessao, FormaPagamento.CREDIARIO) is None


def test_admin_aceita_taxa_zero_dias_zero_e_repasse(sessao, admin):
    novo = atualizar_taxa(sessao, admin, FormaPagamento.DEBITO, D("0"), 0, True)
    assert novo == TaxaForma(FormaPagamento.DEBITO, D("0.00"), 0, True)
    assert taxa_da_forma(sessao, FormaPagamento.DEBITO) == novo


def test_pct_arredonda_em_duas_casas(sessao, admin):
    novo = atualizar_taxa(sessao, admin, FormaPagamento.CREDITO, D("2.555"), 30, False)
    assert novo.pct == D("2.56")


def test_so_admin_altera(sessao, operador):
    with pytest.raises(PermissaoNegada):
        atualizar_taxa(sessao, operador, FormaPagamento.PIX, D("1"), 1, False)
    assert taxa_da_forma(sessao, FormaPagamento.PIX) == TaxaForma(
        FormaPagamento.PIX, D("0.00"), 0, False
    )


@pytest.mark.parametrize(
    ("pct", "dias", "mensagem"),
    [
        (D("-0.01"), 7, "negativa"),
        (D("100.01"), 7, "100%"),
        (D("1.5"), -1, "dias"),
        (D("1.5"), 366, "365"),
        (D("1.5"), 10**9, "365"),
    ],
)
def test_valores_invalidos(sessao, admin, pct, dias, mensagem):
    with pytest.raises(ValorInvalido, match=mensagem):
        atualizar_taxa(sessao, admin, FormaPagamento.DEBITO, pct, dias, False)


def test_dias_ate_o_teto_de_365_sao_aceitos(sessao, admin):
    novo = atualizar_taxa(sessao, admin, FormaPagamento.CREDITO, D("3.5"), 365, False)
    assert novo.dias == 365


def test_crediario_nao_tem_taxa(sessao, admin):
    with pytest.raises(ValorInvalido, match="Crediário"):
        atualizar_taxa(sessao, admin, FormaPagamento.CREDIARIO, D("1"), 0, False)


def test_alteracao_auditada(sessao, admin):
    atualizar_taxa(sessao, admin, FormaPagamento.DEBITO, D("2"), 3, True)
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "taxa_pagamento", AuditLog.acao == "alterar")
    ).one()
    assert (registro.usuario_id, registro.entidade_id) == (admin.id, "DEBITO")
    assert registro.antes == {"pct": "1.50", "dias": 7, "repasse": False}
    assert registro.depois == {"pct": "2.00", "dias": 3, "repasse": True}
