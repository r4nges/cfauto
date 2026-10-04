from datetime import datetime
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from cfauto.caixa.models import (
    FORMAS_COM_TAXA,
    FormaPagamento,
    SessaoCaixa,
    StatusSessao,
    TaxaPagamento,
    TipoVenda,
    Venda,
    VendaItem,
)
from cfauto.clientes.models import MOTIVOS_MANUAIS, Cliente, MotivoLancamento
from cfauto.core.errors import EstoqueInsuficiente, LimiteExcedido
from cfauto.core.migracoes import PASTA_MIGRACOES, migracoes_pendentes
from cfauto.estoque.models import Produto, Servico
from tests.fabricas import criar_cliente_teste, criar_produto, criar_servico


def _sessao_caixa(s, ator, status=StatusSessao.ABERTA, protocolo="CX-20260923-1000"):
    sessao_caixa = SessaoCaixa(
        protocolo=protocolo,
        status=status,
        aberta_em=datetime(2026, 9, 23, 10, 0),
        aberta_por=ator.id,
        fundo_troco=Decimal("100.00"),
    )
    s.add(sessao_caixa)
    s.flush()
    return sessao_caixa


def _venda(s, ator, sessao_caixa):
    venda = Venda(
        sessao_id=sessao_caixa.id,
        data_hora=datetime(2026, 9, 23, 10, 5),
        usuario_id=ator.id,
        tipo=TipoVenda.VENDA,
        forma_pagamento=FormaPagamento.DINHEIRO,
        desconto=Decimal("0"),
        bruto=Decimal("60.00"),
        taxa=Decimal("0"),
        liquido=Decimal("60.00"),
        repasse_taxa=False,
    )
    s.add(venda)
    s.flush()
    return venda


def _item(venda, produto_id=None, servico_id=None, descricao="Óleo 5W30"):
    return VendaItem(
        venda_id=venda.id,
        produto_id=produto_id,
        servico_id=servico_id,
        descricao_snapshot=descricao,
        categoria_snapshot="",
        qtd=Decimal("1"),
        preco_unit=Decimal("30.00"),
        subtotal=Decimal("30.00"),
    )


def _config(conexao):
    cfg = Config()
    cfg.set_main_option("script_location", str(PASTA_MIGRACOES))
    cfg.attributes["connection"] = conexao
    return cfg


def test_taxas_padrao_semeadas(sessao):
    taxas = {t.forma: (t.pct, t.dias, t.repasse) for t in sessao.scalars(select(TaxaPagamento))}
    assert taxas == {
        FormaPagamento.DINHEIRO: (Decimal("0.00"), 0, False),
        FormaPagamento.PIX: (Decimal("0.00"), 0, False),
        FormaPagamento.DEBITO: (Decimal("1.50"), 7, False),
        FormaPagamento.CREDITO: (Decimal("3.50"), 7, False),
    }
    assert set(taxas) == set(FORMAS_COM_TAXA)
    # DecimalEscalado(2) grava inteiro escalado: 1,5% = 150.
    bruto = sessao.execute(text("SELECT pct FROM taxa_pagamento WHERE forma = 'DEBITO'"))
    assert bruto.scalar_one() == 150


def test_banco_impede_duas_sessoes_abertas(sessao, admin):
    _sessao_caixa(sessao, admin, StatusSessao.FECHADA, "CX-20260922-0900")
    _sessao_caixa(sessao, admin)
    with pytest.raises(IntegrityError):
        _sessao_caixa(sessao, admin, protocolo="CX-20260923-1001")
    sessao.rollback()


def test_venda_mistura_produto_e_servico(sessao, admin):
    pid = criar_produto(sessao, admin)
    sid = criar_servico(sessao, admin)
    venda = _venda(sessao, admin, _sessao_caixa(sessao, admin))
    sessao.add(_item(venda, produto_id=pid))
    sessao.add(_item(venda, servico_id=sid, descricao="Troca de óleo"))
    sessao.flush()
    sessao.expire_all()
    venda = sessao.get(Venda, venda.id)
    assert [i.descricao_snapshot for i in venda.itens] == ["Óleo 5W30", "Troca de óleo"]
    assert venda.sessao.protocolo == "CX-20260923-1000"
    assert (venda.cancelada, venda.cliente_id, venda.data_liquidacao) == (False, None, None)


@pytest.mark.parametrize(("com_produto", "com_servico"), [(False, False), (True, True)])
def test_item_exige_produto_ou_servico(sessao, admin, com_produto, com_servico):
    pid = criar_produto(sessao, admin)
    sid = criar_servico(sessao, admin)
    venda = _venda(sessao, admin, _sessao_caixa(sessao, admin))
    sessao.add(
        _item(
            venda,
            produto_id=pid if com_produto else None,
            servico_id=sid if com_servico else None,
        )
    )
    with pytest.raises(IntegrityError):
        sessao.flush()
    sessao.rollback()


def test_fabricas_criam_cadastros(sessao, admin):
    produto = sessao.get(Produto, criar_produto(sessao, admin))
    servico = sessao.get(Servico, criar_servico(sessao, admin))
    cliente = sessao.get(Cliente, criar_cliente_teste(sessao, admin, limite=None))
    assert (produto.preco_venda, produto.estoque) == (Decimal("30.00"), Decimal("10.000"))
    assert servico.preco == Decimal("30.00")
    assert (cliente.nome, cliente.limite) == ("Ana Souza", None)


def test_motivos_manuais_excluem_os_do_caixa():
    assert MOTIVOS_MANUAIS == (
        MotivoLancamento.COMPRA_ANOTADA,
        MotivoLancamento.PAGAMENTO,
        MotivoLancamento.CORRECAO,
        MotivoLancamento.OUTRO,
    )
    assert set(MotivoLancamento) - set(MOTIVOS_MANUAIS) == {
        MotivoLancamento.VENDA_CREDIARIO,
        MotivoLancamento.RECEBIMENTO,
        MotivoLancamento.CANCELAMENTO,
    }


def test_erros_novos_carregam_dados():
    erro = LimiteExcedido("Passou do limite.", Decimal("20.00"), Decimal("10.00"))
    assert (str(erro), erro.disponivel, erro.excesso) == (
        "Passou do limite.",
        Decimal("20.00"),
        Decimal("10.00"),
    )
    assert EstoqueInsuficiente("Falta.").faltas == ()
    falta = ("0001 Óleo 5W30: estoque 1, pedido 3",)
    assert EstoqueInsuficiente("Falta.", falta).faltas == falta


def test_downgrade_para_0003_e_volta(engine):
    with engine.begin() as conexao:
        command.downgrade(_config(conexao), "0003")
    inspetor = inspect(engine)
    novas = {"sessao_caixa", "venda", "venda_item", "taxa_pagamento"}
    assert not novas & set(inspetor.get_table_names())
    assert "venda_id" not in {c["name"] for c in inspetor.get_columns("cliente_lancamento")}
    assert "venda_item_id" not in {c["name"] for c in inspetor.get_columns("movimento_estoque")}
    with engine.begin() as conexao:
        command.upgrade(_config(conexao), "head")
    assert migracoes_pendentes(engine) is False
    with engine.connect() as conexao:
        assert conexao.execute(text("SELECT COUNT(*) FROM taxa_pagamento")).scalar_one() == 4
