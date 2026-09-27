from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from cfauto.core.errors import EanDuplicado, PermissaoNegada, ValorInvalido
from cfauto.core.models import AuditLog
from cfauto.estoque.models import MotivoAjuste, MovimentoEstoque, TipoMovimento
from cfauto.estoque.produtos import (
    ajustar_estoque,
    atualizar_produto,
    buscar_produtos,
    categorias_usadas,
    criar_produto,
    desativar_produto,
    listar_movimentos,
    reativar_produto,
)
from cfauto.estoque.schemas import DadosProduto


def _dados(descricao="Produto", **campos):
    return DadosProduto(descricao=descricao, **campos)


def _criar(sessao, ator, descricao="Produto", **campos):
    return criar_produto(sessao, ator, _dados(descricao, **campos))


def _soma_movimentos(sessao, produto):
    total = sessao.scalar(
        select(func.sum(MovimentoEstoque.quantidade)).where(
            MovimentoEstoque.produto_id == produto.id
        )
    )
    return total or Decimal("0")


def test_criar_gera_codigos_sequenciais_e_carimba_data(sessao, estoquista):
    arroz = _criar(sessao, estoquista, "Arroz")
    feijao = _criar(sessao, estoquista, "Feijão")
    assert (arroz.codigo, feijao.codigo) == ("0001", "0002")
    assert arroz.data_ult_entrada == date(2026, 9, 23)
    assert arroz.estoque == Decimal("0")
    assert _soma_movimentos(sessao, arroz) == Decimal("0")


def test_estoque_inicial_gera_movimento_de_cadastro(sessao, estoquista):
    p = _criar(sessao, estoquista, estoque_inicial=Decimal("2.5"))
    assert p.estoque == Decimal("2.5")
    movimentos = listar_movimentos(sessao, estoquista, p.id)
    assert [(m.tipo, m.quantidade, m.saldo_apos) for m in movimentos] == [
        (TipoMovimento.CADASTRO, Decimal("2.5"), Decimal("2.5"))
    ]
    assert movimentos[0].usuario_nome == "João"


def test_ean_duplicado_e_bloqueado(sessao, estoquista):
    _criar(sessao, estoquista, "Café", ean="7891234567895")
    with pytest.raises(EanDuplicado, match="0001"):
        _criar(sessao, estoquista, "Outro", ean=" 7891234567895 ")


def test_varios_produtos_sem_ean(sessao, estoquista):
    produtos = [
        _criar(sessao, estoquista, nome, ean=ean)
        for nome, ean in [("A", ""), ("B", None), ("C", "  ")]
    ]
    assert [p.ean for p in produtos] == [None, None, None]


@pytest.mark.parametrize("ean", ["78A9", "1" * 15, "７８９"])
def test_ean_invalido(sessao, estoquista, ean):
    with pytest.raises(ValorInvalido, match="EAN"):
        _criar(sessao, estoquista, ean=ean)


@pytest.mark.parametrize(
    ("campos", "mensagem"),
    [
        ({"descricao": "   "}, "Descrição"),
        ({"fator": Decimal("0")}, "fator"),
        ({"fator": Decimal("0.0001")}, "fator"),
        ({"preco_venda": Decimal("-1")}, "negativos"),
        ({"preco_promocional": Decimal("0")}, "promocional"),
        ({"estoque_minimo": Decimal("-1")}, "mínimo"),
        ({"estoque_inicial": Decimal("-1")}, "inicial"),
    ],
)
def test_validacoes_do_cadastro(sessao, estoquista, campos, mensagem):
    dados = {"descricao": "Produto", **campos}
    with pytest.raises(ValorInvalido, match=mensagem):
        criar_produto(sessao, estoquista, DadosProduto(**dados))


def test_fracionado_e_margem(sessao, estoquista):
    p = _criar(
        sessao,
        estoquista,
        fator=Decimal("12"),
        preco_entrada=Decimal("24"),
        preco_venda=Decimal("4"),
    )
    assert p.preco_fracionado == Decimal("2")
    assert p.margem == Decimal("0.5")


def test_edicao_nao_altera_estoque_nem_data(sessao, estoquista, relogio):
    p = _criar(sessao, estoquista, "Arroz", estoque_inicial=Decimal("5"))
    relogio.avancar(days=3)
    atualizar_produto(
        sessao,
        estoquista,
        p.id,
        _dados("Arroz tipo 1", preco_entrada=Decimal("20"), estoque_inicial=Decimal("99")),
    )
    assert p.descricao == "Arroz tipo 1"
    assert p.estoque == Decimal("5")
    assert p.data_ult_entrada == date(2026, 9, 23)
    assert _soma_movimentos(sessao, p) == p.estoque


def test_edicao_audita_antes_e_depois(sessao, estoquista):
    p = _criar(sessao, estoquista, "Arroz", preco_venda=Decimal("10"))
    atualizar_produto(sessao, estoquista, p.id, _dados("Arroz", preco_venda=Decimal("12.5")))
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "produto", AuditLog.acao == "alterar")
    ).one()
    assert registro.antes["preco_venda"] == "10.00"
    assert registro.depois["preco_venda"] == "12.50"


def test_estoque_minimo_manual(sessao, estoquista):
    p = _criar(sessao, estoquista)
    assert p.estoque_minimo_manual is False
    atualizar_produto(sessao, estoquista, p.id, _dados(estoque_minimo=Decimal("3")))
    assert p.estoque_minimo_manual is True
    atualizar_produto(
        sessao,
        estoquista,
        p.id,
        _dados(estoque_minimo=Decimal("3"), estoque_minimo_manual=False),
    )
    assert p.estoque_minimo_manual is False
    com_minimo = _criar(sessao, estoquista, "Com mínimo", estoque_minimo=Decimal("2"))
    assert com_minimo.estoque_minimo_manual is True


def test_ajuste_de_estoque_com_motivo(sessao, estoquista):
    p = _criar(sessao, estoquista, estoque_inicial=Decimal("10"))
    ajustar_estoque(sessao, estoquista, p.id, Decimal("7"), MotivoAjuste.PERDA_AVARIA)
    assert p.estoque == Decimal("7")
    ultimo = listar_movimentos(sessao, estoquista, p.id)[0]
    assert (ultimo.tipo, ultimo.quantidade, ultimo.saldo_apos, ultimo.motivo) == (
        TipoMovimento.AJUSTE,
        Decimal("-3"),
        Decimal("7"),
        MotivoAjuste.PERDA_AVARIA,
    )
    registro = sessao.scalars(select(AuditLog).where(AuditLog.acao == "ajustar_estoque")).one()
    assert registro.antes == {"estoque": "10.000"}
    assert registro.depois["estoque"] == "7.000"
    assert registro.depois["motivo"] == "PERDA_AVARIA"


def test_ajuste_outro_exige_observacao(sessao, estoquista):
    p = _criar(sessao, estoquista, estoque_inicial=Decimal("1"))
    with pytest.raises(ValorInvalido, match="observação"):
        ajustar_estoque(sessao, estoquista, p.id, Decimal("2"), MotivoAjuste.OUTRO, "  ")
    ajustar_estoque(
        sessao, estoquista, p.id, Decimal("2"), MotivoAjuste.OUTRO, "achado no depósito"
    )
    assert listar_movimentos(sessao, estoquista, p.id)[0].observacao == "achado no depósito"


def test_ajuste_sem_diferenca_ou_negativo(sessao, estoquista):
    p = _criar(sessao, estoquista, estoque_inicial=Decimal("1"))
    with pytest.raises(ValorInvalido, match="já está"):
        ajustar_estoque(sessao, estoquista, p.id, Decimal("1"), MotivoAjuste.INVENTARIO)
    with pytest.raises(ValorInvalido, match="negativa"):
        ajustar_estoque(sessao, estoquista, p.id, Decimal("-1"), MotivoAjuste.INVENTARIO)


def test_soma_dos_movimentos_bate_com_estoque(sessao, estoquista):
    p = _criar(sessao, estoquista, estoque_inicial=Decimal("4"))
    for nova in ("10", "3.5", "0", "8"):
        ajustar_estoque(sessao, estoquista, p.id, Decimal(nova), MotivoAjuste.INVENTARIO)
    assert p.estoque == Decimal("8")
    assert _soma_movimentos(sessao, p) == p.estoque


def test_operador_sem_modulo_estoque_e_barrado(sessao, operador):
    with pytest.raises(PermissaoNegada):
        _criar(sessao, operador)
    with pytest.raises(PermissaoNegada):
        buscar_produtos(sessao, operador)


def test_desativar_e_reativar(sessao, estoquista):
    p = _criar(sessao, estoquista, estoque_inicial=Decimal("3"))
    desativar_produto(sessao, estoquista, p.id)
    assert p.ativo is False
    assert buscar_produtos(sessao, estoquista) == []
    assert buscar_produtos(sessao, estoquista, incluir_inativos=True) == [p]
    with pytest.raises(ValorInvalido, match="inativo"):
        desativar_produto(sessao, estoquista, p.id)
    reativar_produto(sessao, estoquista, p.id)
    assert p.ativo is True


@pytest.fixture
def catalogo(sessao, estoquista):
    return {
        "cafe": _criar(sessao, estoquista, "Café Pilão 500g", ean="7891234567895"),
        "cafeteira": _criar(sessao, estoquista, "Cafeteira Elétrica"),
        "acucar": _criar(sessao, estoquista, "Açúcar Cristal 1kg"),
        "pilha": _criar(sessao, estoquista, "Pilha AA Alcalina"),
    }


def _descricoes(produtos):
    return [p.descricao for p in produtos]


def test_busca_vazia_traz_todos_em_ordem_alfabetica(sessao, estoquista, catalogo):
    assert _descricoes(buscar_produtos(sessao, estoquista, "   ")) == [
        "Açúcar Cristal 1kg",
        "Café Pilão 500g",
        "Cafeteira Elétrica",
        "Pilha AA Alcalina",
    ]


def test_busca_por_codigo_sem_zeros_e_por_ean(sessao, estoquista, catalogo):
    assert buscar_produtos(sessao, estoquista, "3") == [catalogo["acucar"]]
    assert buscar_produtos(sessao, estoquista, "0003") == [catalogo["acucar"]]
    assert buscar_produtos(sessao, estoquista, "7891234567895") == [catalogo["cafe"]]


def test_busca_ignora_acento_e_maiusculas_com_prefixo_primeiro(sessao, estoquista, catalogo):
    assert _descricoes(buscar_produtos(sessao, estoquista, "CAFE")) == [
        "Café Pilão 500g",
        "Cafeteira Elétrica",
    ]
    assert buscar_produtos(sessao, estoquista, "acucar") == [catalogo["acucar"]]


def test_busca_exige_todas_as_palavras(sessao, estoquista, catalogo):
    assert buscar_produtos(sessao, estoquista, "pilao cafe") == [catalogo["cafe"]]
    assert buscar_produtos(sessao, estoquista, "alcalina aa") == [catalogo["pilha"]]
    assert buscar_produtos(sessao, estoquista, "cafe xyz") == []


def test_categorias_usadas(sessao, estoquista):
    _criar(sessao, estoquista, "A", categoria="Mercearia")
    _criar(sessao, estoquista, "B", categoria="bebidas")
    _criar(sessao, estoquista, "C", categoria="Mercearia")
    _criar(sessao, estoquista, "D")
    assert categorias_usadas(sessao, estoquista) == ["bebidas", "Mercearia"]
