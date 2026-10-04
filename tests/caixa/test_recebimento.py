from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.caixa.models import FormaPagamento, TipoVenda, Venda
from cfauto.caixa.recebimento import registrar_recebimento
from cfauto.caixa.taxas import atualizar_taxa
from cfauto.caixa.venda import vendas_da_sessao
from cfauto.clientes.models import Cliente, ClienteLancamento, MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar_manual
from cfauto.core.errors import (
    PermissaoNegada,
    RegistroNaoEncontrado,
    SessaoFechada,
    ValorInvalido,
)
from cfauto.core.models import AuditLog
from tests.fabricas import abrir_caixa, criar_cliente_teste

PIX = FormaPagamento.PIX
CREDITO = FormaPagamento.CREDITO
DINHEIRO = FormaPagamento.DINHEIRO


def _com_divida(sessao, admin, valor="100"):
    cid = criar_cliente_teste(sessao, admin)
    lancar_manual(
        sessao,
        admin,
        cid,
        TipoLancamento.DEBITO,
        Decimal(valor),
        MotivoLancamento.COMPRA_ANOTADA,
    )
    return cid


def test_recebimento_lanca_credito_no_razao(sessao, admin, operador):
    cid = _com_divida(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_recebimento(sessao, operador, cid, Decimal("40"), PIX)
    venda = sessao.get(Venda, vid)
    assert (venda.tipo, venda.forma_pagamento, venda.cliente_id, venda.itens) == (
        TipoVenda.RECEBIMENTO,
        PIX,
        cid,
        [],
    )
    assert (venda.desconto, venda.bruto, venda.taxa, venda.liquido) == (
        Decimal("0.00"),
        Decimal("40.00"),
        Decimal("0.00"),
        Decimal("40.00"),
    )
    assert venda.data_liquidacao == date(2026, 9, 23)
    lancamento = sessao.scalars(
        select(ClienteLancamento).where(ClienteLancamento.venda_id == vid)
    ).one()
    assert (lancamento.tipo, lancamento.motivo, lancamento.valor, lancamento.observacao) == (
        TipoLancamento.CREDITO,
        MotivoLancamento.RECEBIMENTO,
        Decimal("40.00"),
        f"Recebimento nº {vid}",
    )
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("60.00")


def test_excedente_vira_credito_a_favor(sessao, admin, operador):
    cid = _com_divida(sessao, admin)
    abrir_caixa(sessao, operador)
    registrar_recebimento(sessao, operador, cid, Decimal("150"), DINHEIRO)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("-50.00")


def test_taxa_do_credito_sem_repasse(sessao, admin, operador):
    cid = _com_divida(sessao, admin)
    abrir_caixa(sessao, operador)
    venda = sessao.get(Venda, registrar_recebimento(sessao, operador, cid, Decimal("100"), CREDITO))
    assert (venda.taxa, venda.liquido, venda.repasse_taxa) == (
        Decimal("3.50"),
        Decimal("96.50"),
        False,
    )
    assert venda.data_liquidacao == date(2026, 9, 30)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")


def test_repasse_cliente_paga_a_taxa_e_divida_abate_o_valor(sessao, admin, operador):
    atualizar_taxa(sessao, admin, CREDITO, Decimal("3.50"), 7, True)
    cid = _com_divida(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_recebimento(sessao, operador, cid, Decimal("100"), CREDITO)
    venda = sessao.get(Venda, vid)
    assert (venda.bruto, venda.taxa, venda.liquido, venda.repasse_taxa) == (
        Decimal("100.00"),
        Decimal("3.50"),
        Decimal("100.00"),
        True,
    )
    linha = vendas_da_sessao(sessao, operador)[0]
    assert (linha.cobrado, linha.descricao, linha.cliente) == (
        Decimal("103.50"),
        "RECEBIMENTO DE CONTA / FIADO",
        "Ana Souza",
    )
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")


def test_cliente_inativo_recusado(sessao, admin, operador):
    cid = criar_cliente_teste(sessao, admin)
    sessao.get(Cliente, cid).ativo = False
    abrir_caixa(sessao, operador)
    with pytest.raises(ValorInvalido, match="inativo"):
        registrar_recebimento(sessao, operador, cid, Decimal("10"), PIX)


def test_cliente_inexistente(sessao, operador):
    abrir_caixa(sessao, operador)
    with pytest.raises(RegistroNaoEncontrado):
        registrar_recebimento(sessao, operador, 999, Decimal("10"), PIX)


def test_forma_crediario_recusada(sessao, admin, operador):
    cid = _com_divida(sessao, admin)
    abrir_caixa(sessao, operador)
    with pytest.raises(ValorInvalido, match="Recebimento"):
        registrar_recebimento(sessao, operador, cid, Decimal("10"), FormaPagamento.CREDIARIO)


@pytest.mark.parametrize("valor", ["0", "-5", "0.004"])
def test_valor_deve_ser_positivo(sessao, admin, operador, valor):
    cid = _com_divida(sessao, admin)
    abrir_caixa(sessao, operador)
    with pytest.raises(ValorInvalido, match="maior que zero"):
        registrar_recebimento(sessao, operador, cid, Decimal(valor), PIX)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("100.00")


def test_sem_sessao_aberta(sessao, admin, operador):
    cid = _com_divida(sessao, admin)
    with pytest.raises(SessaoFechada):
        registrar_recebimento(sessao, operador, cid, Decimal("10"), PIX)


def test_exige_modulo_pdv(sessao, admin, estoquista):
    cid = _com_divida(sessao, admin)
    abrir_caixa(sessao, admin)
    with pytest.raises(PermissaoNegada):
        registrar_recebimento(sessao, estoquista, cid, Decimal("10"), PIX)


def test_auditoria_do_recebimento(sessao, admin, operador):
    cid = _com_divida(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_recebimento(sessao, operador, cid, Decimal("40"), PIX)
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "venda", AuditLog.acao == "criar")
    ).one()
    assert (registro.entidade_id, registro.usuario_id) == (str(vid), operador.id)
    assert registro.depois["tipo"] == "RECEBIMENTO"
    assert registro.depois["saldo_devedor_apos"] == "60.00"
