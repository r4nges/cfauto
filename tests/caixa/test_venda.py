from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.caixa.models import FormaPagamento, TipoVenda, Venda
from cfauto.caixa.schemas import Desconto, ItemVenda, NovaVenda, TipoDesconto
from cfauto.caixa.taxas import atualizar_taxa
from cfauto.caixa.venda import admin_responsavel, registrar_venda, vendas_da_sessao
from cfauto.clientes.models import Cliente, ClienteLancamento, MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar_manual
from cfauto.core.errors import (
    EstoqueInsuficiente,
    LimiteExcedido,
    PermissaoNegada,
    SessaoFechada,
    ValorInvalido,
)
from cfauto.core.models import AuditLog
from cfauto.estoque.models import MovimentoEstoque, Produto, TipoMovimento
from cfauto.estoque.produtos import desativar_produto
from tests.fabricas import abrir_caixa, criar_cliente_teste, criar_produto, criar_servico

DINHEIRO = FormaPagamento.DINHEIRO
DEBITO = FormaPagamento.DEBITO
CREDIARIO = FormaPagamento.CREDIARIO


def _p(produto_id, qtd="1"):
    return ItemVenda(qtd=Decimal(qtd), produto_id=produto_id)


def _s(servico_id, qtd="1"):
    return ItemVenda(qtd=Decimal(qtd), servico_id=servico_id)


def _vendas(sessao):
    return sessao.scalars(select(Venda)).all()


def test_admin_responsavel(admin, operador):
    assert admin_responsavel(admin, None) == admin.id
    assert admin_responsavel(admin, operador) == admin.id
    assert admin_responsavel(operador, None) is None
    assert admin_responsavel(operador, admin) == admin.id
    with pytest.raises(PermissaoNegada, match="administrador"):
        admin_responsavel(operador, operador)


def test_venda_mista_baixa_so_o_produto(sessao, admin, operador):
    pid = criar_produto(sessao, admin, estoque=Decimal("10"))
    sid = criar_servico(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_venda(
        sessao, operador, NovaVenda(itens=(_p(pid, "2"), _s(sid)), forma=DINHEIRO)
    )
    venda = sessao.get(Venda, vid)
    assert (venda.tipo, venda.forma_pagamento, venda.usuario_id) == (
        TipoVenda.VENDA,
        DINHEIRO,
        operador.id,
    )
    assert (venda.desconto, venda.bruto, venda.taxa, venda.liquido) == (
        Decimal("0.00"),
        Decimal("90.00"),
        Decimal("0.00"),
        Decimal("90.00"),
    )
    assert venda.data_liquidacao == date(2026, 9, 23)
    assert venda.autorizado_por is None
    assert venda.cliente_id is None
    assert venda.cancelada is False
    assert [
        (i.descricao_snapshot, i.categoria_snapshot, i.qtd, i.preco_unit, i.subtotal)
        for i in venda.itens
    ] == [
        ("Óleo 5W30", "Lubrificantes", Decimal("2.000"), Decimal("30.00"), Decimal("60.00")),
        ("Troca de óleo", "Serviço", Decimal("1.000"), Decimal("30.00"), Decimal("30.00")),
    ]
    assert venda.itens[1].servico_id == sid and venda.itens[1].produto_id is None
    assert sessao.get(Produto, pid).estoque == Decimal("8.000")
    movimento = sessao.scalars(
        select(MovimentoEstoque).where(MovimentoEstoque.tipo == TipoMovimento.VENDA)
    ).one()
    assert (movimento.quantidade, movimento.venda_item_id, movimento.observacao) == (
        Decimal("-2.000"),
        venda.itens[0].id,
        f"Venda nº {vid}",
    )


def test_preco_vem_do_banco_e_promocional_vale(sessao, admin, operador):
    pid = criar_produto(sessao, admin, preco=Decimal("30.00"), promocional=Decimal("25.00"))
    abrir_caixa(sessao, operador)
    vid = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid, "2"),), forma=DINHEIRO))
    venda = sessao.get(Venda, vid)
    assert (venda.itens[0].preco_unit, venda.bruto) == (Decimal("25.00"), Decimal("50.00"))


def test_desconto_percentual_e_taxa_do_debito(sessao, admin, operador):
    pid = criar_produto(sessao, admin, preco=Decimal("100.00"))
    abrir_caixa(sessao, operador)
    dados = NovaVenda(
        itens=(_p(pid),),
        forma=DEBITO,
        desconto=Desconto(TipoDesconto.PERCENTUAL, Decimal("10")),
    )
    venda = sessao.get(Venda, registrar_venda(sessao, operador, dados))
    assert (venda.desconto, venda.bruto, venda.taxa, venda.liquido, venda.repasse_taxa) == (
        Decimal("10.00"),
        Decimal("90.00"),
        Decimal("1.35"),
        Decimal("88.65"),
        False,
    )
    assert venda.data_liquidacao == date(2026, 9, 30)


def test_repasse_da_taxa_cobra_do_cliente(sessao, admin, operador):
    atualizar_taxa(sessao, admin, DEBITO, Decimal("1.50"), 7, True)
    pid = criar_produto(sessao, admin, preco=Decimal("100.00"))
    abrir_caixa(sessao, operador)
    vid = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DEBITO))
    venda = sessao.get(Venda, vid)
    assert (venda.bruto, venda.taxa, venda.liquido, venda.repasse_taxa) == (
        Decimal("100.00"),
        Decimal("1.50"),
        Decimal("100.00"),
        True,
    )
    assert vendas_da_sessao(sessao, operador)[0].cobrado == Decimal("101.50")


def test_produto_repetido_e_somado_na_checagem_de_estoque(sessao, admin, operador):
    pid = criar_produto(sessao, admin, estoque=Decimal("3"))
    abrir_caixa(sessao, operador)
    dados = NovaVenda(itens=(_p(pid, "2"), _p(pid, "2")), forma=DINHEIRO)
    with pytest.raises(EstoqueInsuficiente, match="administrador") as erro:
        registrar_venda(sessao, operador, dados)
    assert len(erro.value.faltas) == 1
    assert "Óleo 5W30: estoque 3, pedido 4" in erro.value.faltas[0]
    assert _vendas(sessao) == []
    assert sessao.get(Produto, pid).estoque == Decimal("3.000")


def test_operador_com_autorizador_admin_e_confirmacao_vende_sem_estoque(sessao, admin, operador):
    pid = criar_produto(sessao, admin, estoque=Decimal("1"))
    abrir_caixa(sessao, operador)
    dados = NovaVenda(itens=(_p(pid, "3"),), forma=DINHEIRO)
    with pytest.raises(EstoqueInsuficiente):
        registrar_venda(sessao, operador, dados, autorizador=admin)
    assert _vendas(sessao) == []
    vid = registrar_venda(sessao, operador, dados, autorizador=admin, confirmar_estoque=True)
    venda = sessao.get(Venda, vid)
    assert (venda.usuario_id, venda.autorizado_por) == (operador.id, admin.id)
    assert sessao.get(Produto, pid).estoque == Decimal("-2.000")


def test_operador_confirmando_sem_autorizador_continua_barrado(sessao, admin, operador):
    pid = criar_produto(sessao, admin, estoque=Decimal("1"))
    abrir_caixa(sessao, operador)
    with pytest.raises(EstoqueInsuficiente, match="administrador"):
        registrar_venda(
            sessao,
            operador,
            NovaVenda(itens=(_p(pid, "3"),), forma=DINHEIRO),
            confirmar_estoque=True,
        )
    assert _vendas(sessao) == []
    assert sessao.get(Produto, pid).estoque == Decimal("1.000")


def test_autorizador_que_nao_e_admin_e_recusado(sessao, admin, operador):
    pid = criar_produto(sessao, admin, estoque=Decimal("1"))
    abrir_caixa(sessao, operador)
    with pytest.raises(PermissaoNegada, match="administrador"):
        registrar_venda(
            sessao,
            operador,
            NovaVenda(itens=(_p(pid, "3"),), forma=DINHEIRO),
            autorizador=operador,
            confirmar_estoque=True,
        )
    assert _vendas(sessao) == []


def test_admin_logado_sem_confirmacao_recebe_o_aviso(sessao, admin):
    pid = criar_produto(sessao, admin, estoque=Decimal("0"))
    abrir_caixa(sessao, admin)
    with pytest.raises(EstoqueInsuficiente, match="Óleo 5W30: estoque 0, pedido 1"):
        registrar_venda(sessao, admin, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))
    assert _vendas(sessao) == []


def test_admin_logado_confirmando_vende_e_fica_registrado(sessao, admin):
    pid = criar_produto(sessao, admin, estoque=Decimal("0"))
    abrir_caixa(sessao, admin)
    vid = registrar_venda(
        sessao, admin, NovaVenda(itens=(_p(pid),), forma=DINHEIRO), confirmar_estoque=True
    )
    assert sessao.get(Venda, vid).autorizado_por == admin.id
    assert sessao.get(Produto, pid).estoque == Decimal("-1.000")


def test_sem_falta_de_estoque_ignora_autorizacao(sessao, admin, operador):
    pid = criar_produto(sessao, admin, estoque=Decimal("5"))
    abrir_caixa(sessao, operador)
    com_admin = registrar_venda(
        sessao,
        operador,
        NovaVenda(itens=(_p(pid),), forma=DINHEIRO),
        autorizador=admin,
        confirmar_estoque=True,
    )
    com_operador = registrar_venda(
        sessao,
        operador,
        NovaVenda(itens=(_p(pid),), forma=DINHEIRO),
        autorizador=operador,
        confirmar_estoque=True,
    )
    assert sessao.get(Venda, com_admin).autorizado_por is None
    assert sessao.get(Venda, com_operador).autorizado_por is None


def test_crediario_lanca_debito_no_razao(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_venda(
        sessao, operador, NovaVenda(itens=(_p(pid),), forma=CREDIARIO, cliente_id=cid)
    )
    venda = sessao.get(Venda, vid)
    assert (venda.cliente_id, venda.taxa, venda.liquido, venda.data_liquidacao) == (
        cid,
        Decimal("0.00"),
        Decimal("30.00"),
        None,
    )
    lancamento = sessao.scalars(
        select(ClienteLancamento).where(ClienteLancamento.cliente_id == cid)
    ).one()
    assert (
        lancamento.tipo,
        lancamento.motivo,
        lancamento.valor,
        lancamento.venda_id,
        lancamento.observacao,
    ) == (
        TipoLancamento.DEBITO,
        MotivoLancamento.VENDA_CREDIARIO,
        Decimal("30.00"),
        vid,
        f"Venda nº {vid}",
    )
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("30.00")


def test_crediario_exige_cliente(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    abrir_caixa(sessao, operador)
    with pytest.raises(ValorInvalido, match="cliente"):
        registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=CREDIARIO))


def test_crediario_nao_aceita_desconto(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    abrir_caixa(sessao, operador)
    dados = NovaVenda(
        itens=(_p(pid),),
        forma=CREDIARIO,
        cliente_id=cid,
        desconto=Desconto(TipoDesconto.REAIS, Decimal("5")),
    )
    with pytest.raises(ValorInvalido, match="desconto"):
        registrar_venda(sessao, operador, dados)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")


def test_limite_excedido_pede_confirmacao(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    cid = criar_cliente_teste(sessao, admin, limite=Decimal("50.00"))
    abrir_caixa(sessao, operador)
    dados = NovaVenda(itens=(_p(pid, "2"),), forma=CREDIARIO, cliente_id=cid)
    with pytest.raises(LimiteExcedido, match="limite") as erro:
        registrar_venda(sessao, operador, dados)
    assert (erro.value.disponivel, erro.value.excesso) == (Decimal("50.00"), Decimal("10.00"))
    assert _vendas(sessao) == []
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")
    vid = registrar_venda(sessao, operador, dados, confirmar_limite=True)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("60.00")
    registro = sessao.scalars(
        select(AuditLog).where(
            AuditLog.entidade == "venda", AuditLog.acao == "criar", AuditLog.entidade_id == str(vid)
        )
    ).one()
    assert registro.depois["limite_excedido"] == {"disponivel": "50.00", "excesso": "10.00"}


def test_cliente_sem_limite_nao_avisa(sessao, admin, operador):
    pid = criar_produto(sessao, admin, preco=Decimal("1000.00"))
    cid = criar_cliente_teste(sessao, admin, limite=None)
    abrir_caixa(sessao, operador)
    registrar_venda(
        sessao, operador, NovaVenda(itens=(_p(pid, "2"),), forma=CREDIARIO, cliente_id=cid)
    )
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("2000.00")


def test_credito_a_favor_e_consumido_pelo_crediario(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    lancar_manual(
        sessao, admin, cid, TipoLancamento.CREDITO, Decimal("50"), MotivoLancamento.PAGAMENTO
    )
    abrir_caixa(sessao, operador)
    registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=CREDIARIO, cliente_id=cid))
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("-20.00")


def test_sem_sessao_aberta(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    with pytest.raises(SessaoFechada):
        registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))


def test_carrinho_vazio(sessao, operador):
    abrir_caixa(sessao, operador)
    with pytest.raises(ValorInvalido, match="Carrinho vazio"):
        registrar_venda(sessao, operador, NovaVenda(itens=(), forma=DINHEIRO))


@pytest.mark.parametrize("qtd", ["0", "-1", "0.0004"])
def test_quantidade_deve_ser_positiva(sessao, admin, operador, qtd):
    pid = criar_produto(sessao, admin)
    abrir_caixa(sessao, operador)
    with pytest.raises(ValorInvalido, match="quantidade"):
        registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid, qtd),), forma=DINHEIRO))


def test_produto_inativo_recusado(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    desativar_produto(sessao, admin, pid)
    abrir_caixa(sessao, operador)
    with pytest.raises(ValorInvalido, match="inativo"):
        registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))


def test_cliente_inativo_recusado(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    sessao.get(Cliente, cid).ativo = False
    abrir_caixa(sessao, operador)
    with pytest.raises(ValorInvalido, match="inativo"):
        registrar_venda(
            sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO, cliente_id=cid)
        )


def test_exige_modulo_pdv(sessao, admin, estoquista):
    pid = criar_produto(sessao, admin)
    abrir_caixa(sessao, admin)
    with pytest.raises(PermissaoNegada):
        registrar_venda(sessao, estoquista, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))
    with pytest.raises(PermissaoNegada):
        vendas_da_sessao(sessao, estoquista)


def test_auditoria_da_venda(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "venda", AuditLog.acao == "criar")
    ).one()
    assert (registro.entidade_id, registro.usuario_id) == (str(vid), operador.id)
    assert registro.depois["bruto"] == "30.00"
    assert registro.depois["forma"] == "DINHEIRO"
    assert registro.depois["itens"][0]["produto_id"] == pid
    assert registro.depois["limite_excedido"] is None


def test_vendas_da_sessao(sessao, admin, operador, relogio):
    assert vendas_da_sessao(sessao, operador) == []
    pid = criar_produto(sessao, admin)
    sid = criar_servico(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    abrir_caixa(sessao, operador)
    v1 = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))
    relogio.avancar(minutes=5)
    v2 = registrar_venda(
        sessao,
        operador,
        NovaVenda(itens=(_p(pid), _s(sid), _s(sid)), forma=CREDIARIO, cliente_id=cid),
    )
    linhas = vendas_da_sessao(sessao, operador)
    assert [linha.id for linha in linhas] == [v2, v1]
    assert linhas[0].descricao == "Óleo 5W30 (+2 itens)"
    assert (linhas[0].cliente, linhas[0].forma, linhas[0].usuario, linhas[0].cancelada) == (
        "Ana Souza",
        CREDIARIO,
        "Maria",
        False,
    )
    assert (linhas[0].bruto, linhas[0].cobrado) == (Decimal("90.00"), Decimal("90.00"))
    assert (linhas[1].descricao, linhas[1].cliente) == ("Óleo 5W30", None)
