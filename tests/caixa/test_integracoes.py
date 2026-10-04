from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.caixa.models import (
    FormaPagamento,
    SessaoCaixa,
    StatusSessao,
    TipoVenda,
    Venda,
    VendaItem,
)
from cfauto.clientes.cadastro import buscar_clientes, criar_cliente, excluir_cliente, obter_cliente
from cfauto.clientes.models import Cliente, MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar
from cfauto.clientes.schemas import DadosCliente
from cfauto.core.errors import ClienteComHistorico, PermissaoNegada
from cfauto.core.models import AuditLog
from cfauto.core.permissoes import Modulo
from cfauto.estoque.models import Produto, TipoMovimento
from cfauto.estoque.movimentos import movimentar
from cfauto.estoque.produtos import buscar_produtos, criar_produto
from cfauto.estoque.schemas import DadosProduto
from cfauto.estoque.servicos import listar_servicos
from tests import fabricas


@pytest.fixture
def so_pdv(sessao, admin):
    return criar_usuario(
        sessao,
        admin,
        NovoUsuario(nome="Caixa", login="caixa", senha="segredo4", modulos=frozenset({Modulo.PDV})),
    )


def _venda_orm(s, ator, cliente_id=None):
    sessao_caixa = SessaoCaixa(
        protocolo="CX-20260923-1000",
        status=StatusSessao.ABERTA,
        aberta_em=datetime(2026, 9, 23, 10, 0),
        aberta_por=ator.id,
        fundo_troco=Decimal("0"),
    )
    s.add(sessao_caixa)
    s.flush()
    venda = Venda(
        sessao_id=sessao_caixa.id,
        data_hora=datetime(2026, 9, 23, 10, 5),
        usuario_id=ator.id,
        cliente_id=cliente_id,
        tipo=TipoVenda.VENDA,
        forma_pagamento=FormaPagamento.DINHEIRO,
        desconto=Decimal("0"),
        bruto=Decimal("30.00"),
        taxa=Decimal("0"),
        liquido=Decimal("30.00"),
        repasse_taxa=False,
    )
    s.add(venda)
    s.flush()
    return venda


def test_quem_so_tem_pdv_busca_produtos_servicos_e_clientes(sessao, admin, so_pdv):
    fabricas.criar_produto(sessao, admin)
    fabricas.criar_servico(sessao, admin)
    cid = fabricas.criar_cliente_teste(sessao, admin)
    assert [p.descricao for p in buscar_produtos(sessao, so_pdv, "oleo")] == ["Óleo 5W30"]
    assert [sv.nome for sv in listar_servicos(sessao, so_pdv)] == ["Troca de óleo"]
    assert [c.id for c in buscar_clientes(sessao, so_pdv, "ana")] == [cid]
    assert obter_cliente(sessao, so_pdv, cid).dados.nome == "Ana Souza"


def test_so_pdv_continua_sem_cadastrar(sessao, so_pdv):
    with pytest.raises(PermissaoNegada):
        criar_produto(sessao, so_pdv, DadosProduto(descricao="Filtro"))
    with pytest.raises(PermissaoNegada):
        criar_cliente(sessao, so_pdv, DadosCliente(nome="Bia Lima", celular="11912345678"))


def test_lancar_grava_venda_id_e_audita(sessao, admin):
    cid = fabricas.criar_cliente_teste(sessao, admin)
    venda = _venda_orm(sessao, admin, cid)
    lancamento = lancar(
        sessao,
        admin,
        sessao.get(Cliente, cid),
        TipoLancamento.DEBITO,
        Decimal("30"),
        MotivoLancamento.VENDA_CREDIARIO,
        f"Venda nº {venda.id}",
        venda_id=venda.id,
    )
    assert (lancamento.venda_id, lancamento.saldo_apos) == (venda.id, Decimal("30.00"))
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "cliente", AuditLog.acao == "lancamento")
    ).one()
    assert registro.depois["venda_id"] == venda.id


def test_movimentar_grava_venda_item_id(sessao, admin):
    pid = fabricas.criar_produto(sessao, admin)
    venda = _venda_orm(sessao, admin)
    item = VendaItem(
        venda_id=venda.id,
        produto_id=pid,
        descricao_snapshot="Óleo 5W30",
        categoria_snapshot="Lubrificantes",
        qtd=Decimal("1"),
        preco_unit=Decimal("30.00"),
        subtotal=Decimal("30.00"),
    )
    sessao.add(item)
    sessao.flush()
    produto = sessao.get(Produto, pid)
    movimento = movimentar(
        sessao, admin, produto, Decimal("-1"), TipoMovimento.VENDA, venda_item_id=item.id
    )
    assert (movimento.venda_item_id, produto.estoque) == (item.id, Decimal("9.000"))


def test_excluir_cliente_com_venda_bloqueia(sessao, admin):
    cid = fabricas.criar_cliente_teste(sessao, admin)
    _venda_orm(sessao, admin, cid)
    with pytest.raises(ClienteComHistorico, match="vendas registradas"):
        excluir_cliente(sessao, admin, cid)
    assert sessao.get(Cliente, cid) is not None
