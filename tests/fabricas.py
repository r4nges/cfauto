"""Cadastros de apoio para os testes do caixa (funções simples, não fixtures)."""

from decimal import Decimal

from sqlalchemy.orm import Session

from cfauto.caixa.schemas import PainelSessao
from cfauto.caixa.sessao import abrir_sessao
from cfauto.clientes.cadastro import criar_cliente
from cfauto.clientes.schemas import DadosCliente
from cfauto.core.permissoes import Ator
from cfauto.estoque import produtos, servicos
from cfauto.estoque.schemas import DadosMaterial, DadosProduto, DadosServico


def criar_produto(
    s: Session,
    ator: Ator,
    descricao: str = "Óleo 5W30",
    *,
    preco: Decimal = Decimal("30.00"),
    estoque: Decimal = Decimal("10"),
    ean: str | None = None,
    promocional: Decimal | None = None,
    categoria: str = "Lubrificantes",
) -> int:
    produto = produtos.criar_produto(
        s,
        ator,
        DadosProduto(
            descricao=descricao,
            ean=ean,
            categoria=categoria,
            preco_venda=preco,
            preco_promocional=promocional,
            estoque_inicial=estoque,
        ),
    )
    return produto.id


def criar_servico(
    s: Session,
    ator: Ator,
    nome: str = "Troca de óleo",
    *,
    custo: Decimal = Decimal("20.00"),
    mao_obra_pct: Decimal = Decimal(50),
) -> int:
    """Um material de custo `custo`; com 50% de mão de obra o preço fica 30,00."""
    servico = servicos.criar_servico(
        s,
        ator,
        DadosServico(
            nome=nome,
            materiais=(DadosMaterial(descricao="Material", custo_unit=custo),),
            mao_obra_pct=mao_obra_pct,
        ),
    )
    return servico.id


def criar_cliente_teste(
    s: Session,
    ator: Ator,
    nome: str = "Ana Souza",
    *,
    celular: str = "11987654321",
    limite: Decimal | None = Decimal("500.00"),
) -> int:
    return criar_cliente(s, ator, DadosCliente(nome=nome, celular=celular, limite=limite))


def abrir_caixa(s: Session, ator: Ator, fundo: Decimal = Decimal("100.00")) -> PainelSessao:
    return abrir_sessao(s, ator, fundo)
