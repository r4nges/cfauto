from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.caixa.calculo import resumo_de_json
from cfauto.caixa.models import FormaPagamento, SessaoCaixa, Venda
from cfauto.caixa.recebimento import registrar_recebimento
from cfauto.caixa.schemas import ItemVenda, NovaVenda, TotaisForma
from cfauto.caixa.sessao import fechar_sessao, previa_fechamento
from cfauto.caixa.venda import cancelar_venda, registrar_venda, vendas_da_sessao
from cfauto.clientes.models import Cliente, ClienteLancamento, MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar_manual
from cfauto.core.errors import (
    PermissaoNegada,
    RegistroNaoEncontrado,
    SessaoFechada,
    ValorInvalido,
)
from cfauto.core.models import AuditLog
from cfauto.estoque.models import MovimentoEstoque, Produto, TipoMovimento
from tests.fabricas import abrir_caixa, criar_cliente_teste, criar_produto, criar_servico

DINHEIRO = FormaPagamento.DINHEIRO
DEBITO = FormaPagamento.DEBITO
CREDIARIO = FormaPagamento.CREDIARIO


def _p(produto_id, qtd="1"):
    return ItemVenda(qtd=Decimal(qtd), produto_id=produto_id)


def _venda_dinheiro(sessao, admin, operador, qtd="2"):
    pid = criar_produto(sessao, admin, estoque=Decimal("10"))
    abrir_caixa(sessao, operador)
    vid = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid, qtd),), forma=DINHEIRO))
    return pid, vid


def test_admin_cancela_e_estoque_volta(sessao, admin, operador, relogio):
    pid, vid = _venda_dinheiro(sessao, admin, operador)
    relogio.avancar(minutes=3)
    cancelar_venda(sessao, admin, vid, "  Cliente desistiu  ")
    venda = sessao.get(Venda, vid)
    assert venda.cancelada is True
    assert venda.cancelada_em == datetime(2026, 9, 23, 10, 3)
    assert (venda.cancelada_por, venda.cancelamento_autorizado_por) == (admin.id, None)
    assert venda.motivo_cancelamento == "Cliente desistiu"
    assert sessao.get(Produto, pid).estoque == Decimal("10.000")
    movimento = sessao.scalars(
        select(MovimentoEstoque).where(MovimentoEstoque.tipo == TipoMovimento.CANCELAMENTO_VENDA)
    ).one()
    assert (movimento.quantidade, movimento.venda_item_id) == (
        Decimal("2.000"),
        venda.itens[0].id,
    )
    assert vendas_da_sessao(sessao, operador)[0].cancelada is True


def test_operador_cancela_com_autorizacao_do_admin(sessao, admin, operador):
    _, vid = _venda_dinheiro(sessao, admin, operador)
    cancelar_venda(sessao, operador, vid, "Erro de digitação", autorizador=admin)
    venda = sessao.get(Venda, vid)
    assert (venda.cancelada_por, venda.cancelamento_autorizado_por) == (operador.id, admin.id)


def test_operador_sozinho_nao_cancela(sessao, admin, operador):
    _, vid = _venda_dinheiro(sessao, admin, operador)
    with pytest.raises(PermissaoNegada, match="administrador"):
        cancelar_venda(sessao, operador, vid, "Quero cancelar")
    with pytest.raises(PermissaoNegada, match="administrador"):
        cancelar_venda(sessao, operador, vid, "Quero cancelar", autorizador=operador)
    assert sessao.get(Venda, vid).cancelada is False


def test_sessao_fechada_nao_cancela(sessao, admin, operador):
    _, vid = _venda_dinheiro(sessao, admin, operador)
    fechar_sessao(sessao, operador, Decimal("0"))
    with pytest.raises(SessaoFechada, match="não pode mais ser cancelada"):
        cancelar_venda(sessao, admin, vid, "Tarde demais")
    assert sessao.get(Venda, vid).cancelada is False


def test_cancelar_crediario_estorna_o_razao(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_venda(
        sessao, operador, NovaVenda(itens=(_p(pid),), forma=CREDIARIO, cliente_id=cid)
    )
    cancelar_venda(sessao, admin, vid, "Devolução")
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")
    estorno = sessao.scalars(
        select(ClienteLancamento).where(ClienteLancamento.motivo == MotivoLancamento.CANCELAMENTO)
    ).one()
    assert (estorno.tipo, estorno.valor, estorno.venda_id, estorno.observacao) == (
        TipoLancamento.CREDITO,
        Decimal("30.00"),
        vid,
        f"Cancelamento da venda nº {vid}: Devolução",
    )


def test_cancelar_recebimento_devolve_a_divida(sessao, admin, operador):
    cid = criar_cliente_teste(sessao, admin)
    lancar_manual(
        sessao,
        admin,
        cid,
        TipoLancamento.DEBITO,
        Decimal("100"),
        MotivoLancamento.COMPRA_ANOTADA,
    )
    abrir_caixa(sessao, operador)
    vid = registrar_recebimento(sessao, operador, cid, Decimal("100"), FormaPagamento.PIX)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")
    cancelar_venda(sessao, operador, vid, "PIX não caiu", autorizador=admin)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("100.00")
    estorno = sessao.scalars(
        select(ClienteLancamento).where(ClienteLancamento.motivo == MotivoLancamento.CANCELAMENTO)
    ).one()
    assert (estorno.tipo, estorno.valor, estorno.venda_id) == (
        TipoLancamento.DEBITO,
        Decimal("100.00"),
        vid,
    )


def test_estorno_vale_para_cliente_inativo(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_venda(
        sessao, operador, NovaVenda(itens=(_p(pid),), forma=CREDIARIO, cliente_id=cid)
    )
    sessao.get(Cliente, cid).ativo = False
    cancelar_venda(sessao, admin, vid, "Devolução")
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")


@pytest.mark.parametrize("motivo", ["", "   "])
def test_motivo_obrigatorio(sessao, admin, operador, motivo):
    _, vid = _venda_dinheiro(sessao, admin, operador)
    with pytest.raises(ValorInvalido, match="motivo"):
        cancelar_venda(sessao, admin, vid, motivo)


def test_motivo_longo_demais(sessao, admin, operador):
    _, vid = _venda_dinheiro(sessao, admin, operador)
    with pytest.raises(ValorInvalido, match="200"):
        cancelar_venda(sessao, admin, vid, "x" * 201)


def test_motivo_de_200_caracteres_cabe_na_observacao_do_razao(sessao, admin, operador):
    pid = criar_produto(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    abrir_caixa(sessao, operador)
    vid = registrar_venda(
        sessao, operador, NovaVenda(itens=(_p(pid),), forma=CREDIARIO, cliente_id=cid)
    )
    cancelar_venda(sessao, admin, vid, "x" * 200)
    assert sessao.get(Venda, vid).motivo_cancelamento == "x" * 200
    estorno = sessao.scalars(
        select(ClienteLancamento).where(ClienteLancamento.motivo == MotivoLancamento.CANCELAMENTO)
    ).one()
    assert len(estorno.observacao) == 200
    assert estorno.observacao.startswith(f"Cancelamento da venda nº {vid}: ")


def test_nao_cancela_duas_vezes(sessao, admin, operador):
    pid, vid = _venda_dinheiro(sessao, admin, operador)
    cancelar_venda(sessao, admin, vid, "Primeira")
    with pytest.raises(ValorInvalido, match="já está cancelada"):
        cancelar_venda(sessao, admin, vid, "Segunda")
    assert sessao.get(Produto, pid).estoque == Decimal("10.000")


def test_venda_inexistente(sessao, admin):
    abrir_caixa(sessao, admin)
    with pytest.raises(RegistroNaoEncontrado):
        cancelar_venda(sessao, admin, 999, "Não existe")


def test_exige_modulo_pdv(sessao, admin, operador, estoquista):
    _, vid = _venda_dinheiro(sessao, admin, operador)
    with pytest.raises(PermissaoNegada):
        cancelar_venda(sessao, estoquista, vid, "Sem acesso", autorizador=admin)


def test_auditoria_do_cancelamento(sessao, admin, operador):
    _, vid = _venda_dinheiro(sessao, admin, operador)
    cancelar_venda(sessao, operador, vid, "Erro", autorizador=admin)
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "venda", AuditLog.acao == "cancelar")
    ).one()
    assert (registro.entidade_id, registro.usuario_id) == (str(vid), operador.id)
    assert registro.antes == {"cancelada": False}
    assert registro.depois == {
        "cancelada": True,
        "motivo": "Erro",
        "cancelamento_autorizado_por": admin.id,
    }


def test_fechamento_integra_vendas_recebimentos_e_canceladas(sessao, admin, operador, relogio):
    pid = criar_produto(sessao, admin, preco=Decimal("50.00"), estoque=Decimal("20"))
    sid = criar_servico(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    painel = abrir_caixa(sessao, operador, Decimal("100"))
    registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))
    registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid, "2"),), forma=DEBITO))
    registrar_venda(
        sessao,
        operador,
        NovaVenda(
            itens=(ItemVenda(qtd=Decimal("1"), servico_id=sid),),
            forma=CREDIARIO,
            cliente_id=cid,
        ),
    )
    cancelada = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))
    cancelar_venda(sessao, admin, cancelada, "Erro de digitação")
    registrar_recebimento(sessao, operador, cid, Decimal("20"), DINHEIRO)

    resumo = previa_fechamento(sessao, operador)
    assert list(resumo.vendas) == [DINHEIRO, DEBITO, CREDIARIO]
    assert resumo.vendas[DINHEIRO] == TotaisForma(
        qtd=1,
        bruto=Decimal("50.00"),
        taxa=Decimal("0.00"),
        liquido=Decimal("50.00"),
        cobrado=Decimal("50.00"),
    )
    assert resumo.vendas[DEBITO] == TotaisForma(
        qtd=1,
        bruto=Decimal("100.00"),
        taxa=Decimal("1.50"),
        liquido=Decimal("98.50"),
        cobrado=Decimal("100.00"),
    )
    assert resumo.vendas[CREDIARIO] == TotaisForma(
        qtd=1,
        bruto=Decimal("30.00"),
        taxa=Decimal("0.00"),
        liquido=Decimal("30.00"),
        cobrado=Decimal("30.00"),
    )
    assert resumo.recebimentos == {
        DINHEIRO: TotaisForma(
            qtd=1,
            bruto=Decimal("20.00"),
            taxa=Decimal("0.00"),
            liquido=Decimal("20.00"),
            cobrado=Decimal("20.00"),
        )
    }
    assert (resumo.canceladas_qtd, resumo.canceladas_bruto) == (1, Decimal("50.00"))
    assert resumo.total_vendido == Decimal("180.00")
    assert resumo.dinheiro == Decimal("70.00")
    assert resumo.gaveta == Decimal("170.00")

    fechamento = fechar_sessao(sessao, operador, Decimal("100"))
    assert fechamento.sangria == Decimal("70.00")
    registro = sessao.get(SessaoCaixa, painel.id)
    assert resumo_de_json(registro.resumo_json) == resumo
    assert sessao.get(Produto, pid).estoque == Decimal("17.000")
