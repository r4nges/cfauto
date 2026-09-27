from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from cfauto.estoque.models import NotaEntrada, Produto, Servico, ServicoMaterial


def test_tabelas_do_estoque_existem(engine):
    tabelas = set(inspect(engine).get_table_names())
    assert {
        "sequencia",
        "produto",
        "servico",
        "servico_material",
        "movimento_estoque",
        "nota_entrada",
        "nota_entrada_item",
        "vinculo_fornecedor_produto",
        "bem_fisico",
    } <= tabelas


def test_preco_fracionado_e_margem():
    p = Produto(preco_entrada=Decimal("12.00"), fator=Decimal("12"), preco_venda=Decimal("2.00"))
    assert p.preco_fracionado == Decimal("1")
    assert p.margem == Decimal("0.5")


def test_margem_sem_preco_de_venda_ou_custo_e_none():
    sem_venda = Produto(preco_entrada=Decimal("1"), fator=Decimal("1"), preco_venda=Decimal("0"))
    sem_custo = Produto(preco_entrada=Decimal("0"), fator=Decimal("1"), preco_venda=Decimal("5"))
    assert sem_venda.margem is None
    assert sem_custo.margem is None


def test_preco_do_servico():
    servico = Servico(
        mao_obra_pct=Decimal("50"),
        materiais=[
            ServicoMaterial(descricao="Tomada", custo_unit=Decimal("2.50"), qtd=Decimal("2")),
            ServicoMaterial(descricao="Fita", custo_unit=Decimal("1.00"), qtd=Decimal("1")),
        ],
    )
    assert servico.custo_materiais == Decimal("6.00")
    assert servico.preco == Decimal("9.00")


def _nota(chave: str, usuario_id: int, estornada: bool = False) -> NotaEntrada:
    return NotaEntrada(
        chave=chave,
        numero=1,
        serie=1,
        modelo=55,
        emitente_cnpj="12345678000195",
        emitente_nome="Fornecedor",
        data_emissao=date(2026, 9, 20),
        data_entrada=datetime(2026, 9, 23, 10, 0),
        valor_total=Decimal("10.00"),
        usuario_id=usuario_id,
        xml_original=b"<NFe/>",
        estornada=estornada,
    )


def test_chave_unica_so_entre_notas_nao_estornadas(sessao, admin):
    sessao.add(_nota("1" * 44, admin.id, estornada=True))
    sessao.add(_nota("1" * 44, admin.id))
    sessao.flush()
    sessao.add(_nota("1" * 44, admin.id))
    with pytest.raises(IntegrityError):
        sessao.flush()
    sessao.rollback()
