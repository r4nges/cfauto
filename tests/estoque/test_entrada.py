from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from cfauto.core import config
from cfauto.core.errors import NotaJaImportada, PermissaoNegada, ValorInvalido
from cfauto.core.models import AuditLog
from cfauto.estoque.entrada import confirmar_entrada, preparar_entrada
from cfauto.estoque.models import (
    MovimentoEstoque,
    NotaEntrada,
    Produto,
    TipoMovimento,
    VinculoFornecedorProduto,
)
from cfauto.estoque.produtos import criar_produto, desativar_produto
from cfauto.estoque.schemas import AcaoItem, DadosProduto, DecisaoItem, OrigemCasamento
from tests.estoque.xml_nfe import CNPJ_FORNECEDOR, ItemXml, montar_nfe

EAN_REFRI = "7891000100103"


def _produto(sessao, ator, descricao="Produto", **campos):
    return criar_produto(sessao, ator, DadosProduto(descricao=descricao, **campos))


def _vincular(n_item, produto, fator):
    return DecisaoItem(n_item, AcaoItem.VINCULAR, produto_id=produto.id, fator=Decimal(fator))


def _vinculo(sessao, codigo, produto, fator):
    sessao.add(
        VinculoFornecedorProduto(
            emitente_cnpj=CNPJ_FORNECEDOR,
            codigo_fornecedor=codigo,
            produto_id=produto.id,
            fator=Decimal(fator),
        )
    )
    sessao.flush()


def test_sugere_pelo_ean_com_o_fator_do_produto(sessao, estoquista):
    p = _produto(sessao, estoquista, "Refrigerante Cola 2L", ean=EAN_REFRI)
    xml = montar_nfe(1, [ItemXml("A-100", "REFRIGERANTE COLA 2L", "10", "75.00", ean=EAN_REFRI)])
    item = preparar_entrada(sessao, estoquista, xml).itens[0]
    assert (item.origem, item.produto_id, item.fator_sugerido) == (
        OrigemCasamento.EAN,
        p.id,
        Decimal("1"),
    )
    assert (item.produto_codigo, item.produto_descricao) == ("0001", "Refrigerante Cola 2L")


def test_sugere_pelo_ean_tributavel(sessao, estoquista):
    p = _produto(sessao, estoquista, "Água mineral 500ml", ean="7891000300312")
    xml = montar_nfe(
        1,
        [
            ItemXml(
                "C-300",
                "AGUA FD C/12",
                "3",
                "36.00",
                ean="7891000300305",
                ean_trib="7891000300312",
                unidade="FD",
                unidade_trib="UN",
                qtd_trib="36",
            )
        ],
    )
    item = preparar_entrada(sessao, estoquista, xml).itens[0]
    assert (item.origem, item.produto_id, item.fator_sugerido) == (
        OrigemCasamento.EAN_TRIB,
        p.id,
        Decimal("12"),
    )


def test_vinculo_tem_prioridade_sobre_o_ean(sessao, estoquista):
    _produto(sessao, estoquista, "Refri avulso", ean=EAN_REFRI)
    fardo = _produto(sessao, estoquista, "Refri fardo", fator=Decimal("6"))
    _vinculo(sessao, "A-100", fardo, "6")
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "1", "40.00", ean=EAN_REFRI)])
    item = preparar_entrada(sessao, estoquista, xml).itens[0]
    assert (item.origem, item.produto_id, item.fator_sugerido) == (
        OrigemCasamento.VINCULO,
        fardo.id,
        Decimal("6"),
    )


def test_vinculo_para_produto_inativo_e_ignorado(sessao, estoquista):
    velho = _produto(sessao, estoquista, "Velho")
    _vinculo(sessao, "A-100", velho, "1")
    desativar_produto(sessao, estoquista, velho.id)
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "1", "4.00")])
    assert preparar_entrada(sessao, estoquista, xml).itens[0].origem is OrigemCasamento.NENHUMA


def test_descricao_parecida_nunca_casa(sessao, estoquista):
    _produto(sessao, estoquista, "REFRIGERANTE COLA 2L")
    xml = montar_nfe(1, [ItemXml("A-100", "REFRIGERANTE COLA 2L", "1", "7.50")])
    item = preparar_entrada(sessao, estoquista, xml).itens[0]
    assert (item.origem, item.produto_id) == (OrigemCasamento.NENHUMA, None)


def test_confirmar_lanca_estoque_custo_e_data(sessao, estoquista, relogio):
    p = _produto(
        sessao,
        estoquista,
        "Refri",
        ean=EAN_REFRI,
        embalagem="Caixa c/12",
        fator=Decimal("12"),
        preco_entrada=Decimal("60"),
        estoque_inicial=Decimal("5"),
    )
    relogio.avancar(days=2)
    xml = montar_nfe(
        1, [ItemXml("A-100", "REFRI CX12", "2", "150.00", ean=EAN_REFRI, unidade="CX", ipi="6.00")]
    )
    nota = confirmar_entrada(sessao, estoquista, xml, [_vincular(1, p, "12")])
    assert p.estoque == Decimal("29")
    assert p.preco_entrada == Decimal("78.0000")  # 156 / 24 un × 12 un por caixa
    assert p.preco_fracionado == Decimal("6.5")
    assert p.data_ult_entrada == date(2026, 9, 25)
    assert (p.embalagem, p.fator) == ("Caixa c/12", Decimal("12"))
    item = nota.itens[0]
    assert (
        item.qtd_estoque,
        item.custo_total,
        item.preco_entrada_anterior,
        item.data_ult_entrada_anterior,
    ) == (Decimal("24"), Decimal("156.00"), Decimal("60"), date(2026, 9, 23))
    movimento = sessao.scalars(
        select(MovimentoEstoque).where(MovimentoEstoque.tipo == TipoMovimento.ENTRADA_NF)
    ).one()
    assert (movimento.quantidade, movimento.saldo_apos, movimento.nota_entrada_item_id) == (
        Decimal("24"),
        Decimal("29"),
        item.id,
    )
    vinculo = sessao.scalars(select(VinculoFornecedorProduto)).one()
    assert (vinculo.codigo_fornecedor, vinculo.produto_id, vinculo.fator) == (
        "A-100",
        p.id,
        Decimal("12"),
    )
    auditoria = sessao.scalars(select(AuditLog).where(AuditLog.acao == "entrada")).one()
    assert (auditoria.depois["itens_lancados"], auditoria.depois["itens_ignorados"]) == (1, 0)


def test_vinculo_e_reaproveitado_na_nota_seguinte(sessao, estoquista):
    p = _produto(sessao, estoquista, "Parafuso", fator=Decimal("100"))
    primeira = montar_nfe(1, [ItemXml("B-200", "PARAFUSO CX", "1", "15.00", unidade="CX")])
    confirmar_entrada(sessao, estoquista, primeira, [_vincular(1, p, "100")])
    segunda = montar_nfe(2, [ItemXml("B-200", "PARAFUSO CX", "3", "45.00", unidade="CX")])
    item = preparar_entrada(sessao, estoquista, segunda).itens[0]
    assert (item.origem, item.produto_id, item.fator_sugerido) == (
        OrigemCasamento.VINCULO,
        p.id,
        Decimal("100"),
    )


def test_criar_produto_pela_nota(sessao, estoquista):
    xml = montar_nfe(
        1,
        [
            ItemXml(
                "B-200",
                "PARAFUSO SEXTAVADO",
                "2",
                "30.00",
                unidade="CX",
                unidade_trib="UN",
                qtd_trib="200",
            )
        ],
    )
    assert preparar_entrada(sessao, estoquista, xml).itens[0].fator_sugerido == Decimal("100")
    decisao = DecisaoItem(
        1, AcaoItem.CRIAR, descricao="  Parafuso sextavado 1/4  ", fator=Decimal("100")
    )
    novo = confirmar_entrada(sessao, estoquista, xml, [decisao]).itens[0].produto
    assert (novo.codigo, novo.descricao, novo.embalagem, novo.fator, novo.ean) == (
        "0001",
        "Parafuso sextavado 1/4",
        "CX",
        Decimal("100"),
        None,
    )
    assert novo.estoque == Decimal("200")
    assert novo.preco_entrada == Decimal("15.0000")
    assert novo.data_ult_entrada == date(2026, 9, 23)


def test_criar_usa_o_ean_e_a_descricao_da_nota(sessao, estoquista):
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "1", "7.50", ean=EAN_REFRI)])
    decisao = DecisaoItem(1, AcaoItem.CRIAR, fator=Decimal("1"))
    novo = confirmar_entrada(sessao, estoquista, xml, [decisao]).itens[0].produto
    assert (novo.ean, novo.descricao) == (EAN_REFRI, "REFRI")


def test_mesmo_ean_novo_em_dois_itens_nao_quebra(sessao, estoquista):
    xml = montar_nfe(
        1,
        [
            ItemXml("A-100", "REFRI", "1", "7.50", ean=EAN_REFRI),
            ItemXml("A-101", "REFRI BRINDE", "1", "7.50", ean=EAN_REFRI),
        ],
    )
    decisoes = [DecisaoItem(n, AcaoItem.CRIAR, fator=Decimal("1")) for n in (1, 2)]
    nota = confirmar_entrada(sessao, estoquista, xml, decisoes)
    assert [i.produto.ean for i in nota.itens] == [EAN_REFRI, None]


def test_ignorar_item(sessao, estoquista):
    xml = montar_nfe(1, [ItemXml("Z-1", "SACOLA PLASTICA", "100", "5.00")])
    nota = confirmar_entrada(sessao, estoquista, xml, [DecisaoItem(1, AcaoItem.IGNORAR)])
    assert nota.itens[0].produto_id is None
    assert sessao.scalar(select(func.count()).select_from(Produto)) == 0
    assert sessao.scalar(select(func.count()).select_from(MovimentoEstoque)) == 0
    auditoria = sessao.scalars(select(AuditLog).where(AuditLog.acao == "entrada")).one()
    assert auditoria.depois["itens_ignorados"] == 1


def test_bonificacao_soma_estoque_sem_zerar_custo(sessao, estoquista):
    p = _produto(sessao, estoquista, "Refri", preco_entrada=Decimal("7.50"))
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI BONIFICACAO", "6", "0.00")])
    confirmar_entrada(sessao, estoquista, xml, [_vincular(1, p, "1")])
    assert p.estoque == Decimal("6")
    assert p.preco_entrada == Decimal("7.50")


def test_quantidade_fracionada(sessao, estoquista):
    p = _produto(sessao, estoquista, "Queijo mussarela", embalagem="KG")
    xml = montar_nfe(1, [ItemXml("D-400", "QUEIJO MUSSARELA", "2.5000", "87.50", unidade="KG")])
    confirmar_entrada(sessao, estoquista, xml, [_vincular(1, p, "1")])
    assert p.estoque == Decimal("2.5")
    assert p.preco_entrada == Decimal("35.0000")


def test_nota_duplicada_e_bloqueada(sessao, estoquista):
    p = _produto(sessao, estoquista)
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "1", "7.50")])
    confirmar_entrada(sessao, estoquista, xml, [_vincular(1, p, "1")])
    with pytest.raises(NotaJaImportada, match="Distribuidora"):
        preparar_entrada(sessao, estoquista, xml)
    with pytest.raises(NotaJaImportada):
        confirmar_entrada(sessao, estoquista, xml, [_vincular(1, p, "1")])


@pytest.mark.parametrize(
    ("decisoes", "mensagem"),
    [
        (lambda p: [], "sem decisão"),
        (lambda p: [_vincular(1, p, "1"), _vincular(2, p, "1")], "não existem"),
        (lambda p: [_vincular(1, p, "1"), _vincular(1, p, "1")], "mais de uma vez"),
        (lambda p: [DecisaoItem(1, AcaoItem.VINCULAR, fator=Decimal("1"))], "produto ativo"),
        (lambda p: [DecisaoItem(1, AcaoItem.VINCULAR, produto_id=p.id)], "fator"),
        (lambda p: [_vincular(1, p, "0")], "fator"),
        (
            lambda p: [DecisaoItem(1, AcaoItem.CRIAR, descricao="  ", fator=Decimal("1"))],
            "descrição",
        ),
    ],
)
def test_decisoes_invalidas_nao_gravam_nada(sessao, estoquista, decisoes, mensagem):
    p = _produto(sessao, estoquista)
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "1", "7.50")])
    with pytest.raises(ValorInvalido, match=mensagem):
        confirmar_entrada(sessao, estoquista, xml, decisoes(p))
    assert sessao.scalar(select(func.count()).select_from(NotaEntrada)) == 0
    assert p.estoque == Decimal("0")


def test_vincular_produto_inativo_e_rejeitado(sessao, estoquista):
    p = _produto(sessao, estoquista)
    desativar_produto(sessao, estoquista, p.id)
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "1", "7.50")])
    with pytest.raises(ValorInvalido, match="produto ativo"):
        confirmar_entrada(sessao, estoquista, xml, [_vincular(1, p, "1")])


def test_operador_sem_estoque_e_barrado(sessao, operador):
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "1", "7.50")])
    with pytest.raises(PermissaoNegada):
        preparar_entrada(sessao, operador, xml)


def test_aviso_quando_o_destinatario_nao_e_a_empresa(sessao, estoquista):
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "1", "7.50")])
    assert preparar_entrada(sessao, estoquista, xml).avisos == ()
    config.definir(sessao, "empresa.cnpj", "11.111.111/0001-11")
    assert "11111111000111" in preparar_entrada(sessao, estoquista, xml).avisos[0]
    config.definir(sessao, "empresa.cnpj", "98.765.432/0001-10")
    assert preparar_entrada(sessao, estoquista, xml).avisos == ()
