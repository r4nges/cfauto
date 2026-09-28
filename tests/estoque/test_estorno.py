from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from cfauto.core.errors import EstoqueInsuficiente, PermissaoNegada, ValorInvalido
from cfauto.core.models import AuditLog
from cfauto.estoque.entrada import (
    confirmar_entrada,
    estornar_entrada,
    listar_notas,
    obter_nota,
    preparar_entrada,
)
from cfauto.estoque.models import MotivoAjuste, MovimentoEstoque, Produto, TipoMovimento
from cfauto.estoque.produtos import ajustar_estoque, atualizar_produto, criar_produto
from cfauto.estoque.schemas import AcaoItem, DadosProduto, DecisaoItem
from tests.estoque.xml_nfe import ItemXml, montar_nfe


def _produto(sessao, ator, **campos):
    dados = {
        "descricao": "Refri",
        "preco_entrada": Decimal("60"),
        "fator": Decimal("12"),
        "estoque_inicial": Decimal("5"),
        **campos,
    }
    return criar_produto(sessao, ator, DadosProduto(**dados))


def _entrada(sessao, ator, numero, produto, qtd="2", valor="150.00", fator="12"):
    xml = montar_nfe(numero, [ItemXml("A-100", "REFRI CX12", qtd, valor, unidade="CX")])
    decisao = DecisaoItem(1, AcaoItem.VINCULAR, produto_id=produto.id, fator=Decimal(fator))
    return confirmar_entrada(sessao, ator, xml, [decisao])


def _soma(sessao, produto):
    return sessao.scalar(
        select(func.sum(MovimentoEstoque.quantidade)).where(
            MovimentoEstoque.produto_id == produto.id
        )
    )


def test_estorno_reverte_estoque_e_restaura_preco_e_data(sessao, admin, relogio):
    p = _produto(sessao, admin)
    relogio.avancar(days=2)
    nota = _entrada(sessao, admin, 1, p)
    assert (p.estoque, p.preco_entrada) == (Decimal("29"), Decimal("75.0000"))
    relogio.avancar(days=1)
    estornar_entrada(sessao, admin, nota.id)
    assert (p.estoque, p.preco_entrada, p.data_ult_entrada) == (
        Decimal("5"),
        Decimal("60"),
        date(2026, 9, 23),
    )
    assert nota.estornada is True
    assert nota.estornada_por == admin.id
    ultimo = sessao.scalars(select(MovimentoEstoque).order_by(MovimentoEstoque.id.desc())).first()
    assert (ultimo.tipo, ultimo.quantidade, ultimo.saldo_apos) == (
        TipoMovimento.ESTORNO_NF,
        Decimal("-24"),
        Decimal("5"),
    )
    auditoria = sessao.scalars(select(AuditLog).where(AuditLog.acao == "estornar")).one()
    assert auditoria.entidade_id == str(nota.id)
    assert _soma(sessao, p) == p.estoque


def test_entrada_posterior_mantem_o_preco(sessao, admin):
    p = _produto(sessao, admin)
    primeira = _entrada(sessao, admin, 1, p)
    _entrada(sessao, admin, 2, p, valor="180.00")
    assert p.preco_entrada == Decimal("90.0000")
    estornar_entrada(sessao, admin, primeira.id)
    assert p.preco_entrada == Decimal("90.0000")
    assert p.estoque == Decimal("29")


def test_edicao_manual_depois_da_entrada_mantem_o_preco(sessao, admin):
    p = _produto(sessao, admin)
    nota = _entrada(sessao, admin, 1, p)
    atualizar_produto(
        sessao,
        admin,
        p.id,
        DadosProduto(descricao="Refri", fator=Decimal("12"), preco_entrada=Decimal("99")),
    )
    estornar_entrada(sessao, admin, nota.id)
    assert p.preco_entrada == Decimal("99")


def test_mesmo_produto_em_dois_itens_restaura_o_original(sessao, admin):
    p = _produto(sessao, admin)
    xml = montar_nfe(
        1,
        [
            ItemXml("A-100", "REFRI", "1", "72.00", unidade="CX"),
            ItemXml("A-100", "REFRI", "1", "84.00", unidade="CX"),
        ],
    )
    decisoes = [
        DecisaoItem(n, AcaoItem.VINCULAR, produto_id=p.id, fator=Decimal("12")) for n in (1, 2)
    ]
    nota = confirmar_entrada(sessao, admin, xml, decisoes)
    assert p.preco_entrada == Decimal("84.0000")
    estornar_entrada(sessao, admin, nota.id)
    assert (p.preco_entrada, p.estoque) == (Decimal("60"), Decimal("5"))


def test_estorno_nunca_apaga_produto_criado_pela_nota(sessao, admin):
    xml = montar_nfe(1, [ItemXml("B-200", "PARAFUSO", "2", "30.00", unidade="CX")])
    decisao = DecisaoItem(1, AcaoItem.CRIAR, fator=Decimal("100"))
    nota = confirmar_entrada(sessao, admin, xml, [decisao])
    novo = nota.itens[0].produto
    estornar_entrada(sessao, admin, nota.id)
    assert sessao.get(Produto, novo.id) is novo
    assert (novo.estoque, novo.ativo) == (Decimal("0"), True)


def test_estorno_que_deixa_saldo_negativo_exige_confirmacao(sessao, admin):
    p = _produto(sessao, admin)
    nota = _entrada(sessao, admin, 1, p)
    ajustar_estoque(sessao, admin, p.id, Decimal("1"), MotivoAjuste.PERDA_AVARIA)
    with pytest.raises(EstoqueInsuficiente, match="0001"):
        estornar_entrada(sessao, admin, nota.id)
    assert p.estoque == Decimal("1")
    assert nota.estornada is False
    estornar_entrada(sessao, admin, nota.id, confirmar_negativo=True)
    assert p.estoque == Decimal("-23")


def test_estorno_so_admin(sessao, estoquista):
    p = _produto(sessao, estoquista)
    nota = _entrada(sessao, estoquista, 1, p)
    with pytest.raises(PermissaoNegada):
        estornar_entrada(sessao, estoquista, nota.id)


def test_estorno_duplo_rejeitado(sessao, admin):
    p = _produto(sessao, admin)
    nota = _entrada(sessao, admin, 1, p)
    estornar_entrada(sessao, admin, nota.id)
    with pytest.raises(ValorInvalido, match="já foi estornada"):
        estornar_entrada(sessao, admin, nota.id)


def test_reimportar_nota_estornada(sessao, admin):
    p = _produto(sessao, admin)
    nota = _entrada(sessao, admin, 1, p)
    estornar_entrada(sessao, admin, nota.id)
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI CX12", "2", "150.00", unidade="CX")])
    assert preparar_entrada(sessao, admin, xml).itens[0].produto_id == p.id  # o vínculo ficou
    nova = _entrada(sessao, admin, 1, p)
    assert nova.id != nota.id
    assert nova.chave == nota.chave
    assert p.estoque == Decimal("29")


def test_listar_e_obter_notas(sessao, admin, relogio):
    p = _produto(sessao, admin)
    antiga = _entrada(sessao, admin, 1, p)
    relogio.avancar(hours=1)
    recente = _entrada(sessao, admin, 2, p)
    estornar_entrada(sessao, admin, antiga.id)
    assert [n.id for n in listar_notas(sessao, admin)] == [recente.id, antiga.id]
    detalhe = obter_nota(sessao, admin, antiga.id)
    assert detalhe.itens[0].produto.codigo == "0001"
