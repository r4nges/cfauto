from decimal import Decimal

import pytest
from sqlalchemy import func, select

from cfauto.core.errors import PermissaoNegada, ValorInvalido
from cfauto.core.models import AuditLog
from cfauto.estoque.models import ServicoMaterial
from cfauto.estoque.schemas import DadosMaterial, DadosServico
from cfauto.estoque.servicos import (
    atualizar_servico,
    criar_servico,
    desativar_servico,
    listar_servicos,
    reativar_servico,
)

TOMADA = DadosServico(
    nome="Troca de tomada",
    materiais=(
        DadosMaterial("Tomada", Decimal("2.50"), Decimal("2")),
        DadosMaterial("Fita isolante", Decimal("1.00")),
    ),
    mao_obra_pct=Decimal("50"),
)


def test_criar_servico_calcula_preco_e_audita(sessao, estoquista):
    servico = criar_servico(sessao, estoquista, TOMADA)
    assert servico.codigo == "SERV-001"
    assert (servico.custo_materiais, servico.preco) == (Decimal("6.00"), Decimal("9.00"))
    registro = sessao.scalars(select(AuditLog).where(AuditLog.entidade == "servico")).one()
    assert registro.depois["preco"] == "9.00"
    assert len(registro.depois["materiais"]) == 2


def test_editar_substitui_materiais(sessao, estoquista):
    servico = criar_servico(sessao, estoquista, TOMADA)
    atualizar_servico(
        sessao,
        estoquista,
        servico.id,
        DadosServico(
            nome="Troca de tomada dupla",
            materiais=(DadosMaterial("Tomada dupla", Decimal("8")),),
            mao_obra_pct=Decimal("25"),
        ),
    )
    assert sessao.scalar(select(func.count()).select_from(ServicoMaterial)) == 1
    assert (servico.nome, servico.preco) == ("Troca de tomada dupla", Decimal("10.00"))


@pytest.mark.parametrize(
    ("dados", "mensagem"),
    [
        (DadosServico(nome=" ", materiais=TOMADA.materiais), "Nome"),
        (DadosServico(nome="X", materiais=()), "ao menos um material"),
        (
            DadosServico(nome="X", materiais=(DadosMaterial(" ", Decimal("1")),)),
            "Material 1: descrição",
        ),
        (
            DadosServico(nome="X", materiais=(DadosMaterial("Fio", Decimal("0")),)),
            "Material 1: custo",
        ),
        (
            DadosServico(nome="X", materiais=(DadosMaterial("Fio", Decimal("1"), Decimal("0")),)),
            "Material 1: quantidade",
        ),
        (
            DadosServico(nome="X", materiais=TOMADA.materiais, mao_obra_pct=Decimal("-1")),
            "Mão de obra",
        ),
    ],
)
def test_validacoes(sessao, estoquista, dados, mensagem):
    with pytest.raises(ValorInvalido, match=mensagem):
        criar_servico(sessao, estoquista, dados)


def test_listar_ignora_inativos(sessao, estoquista):
    tomada = criar_servico(sessao, estoquista, TOMADA)
    chuveiro = criar_servico(
        sessao,
        estoquista,
        DadosServico(
            nome="Instalação de chuveiro", materiais=(DadosMaterial("Cabo", Decimal("10")),)
        ),
    )
    desativar_servico(sessao, estoquista, tomada.id)
    assert listar_servicos(sessao, estoquista) == [chuveiro]
    assert listar_servicos(sessao, estoquista, incluir_inativos=True) == [chuveiro, tomada]
    reativar_servico(sessao, estoquista, tomada.id)
    assert tomada.ativo is True


def test_operador_sem_estoque_e_barrado(sessao, operador):
    with pytest.raises(PermissaoNegada):
        criar_servico(sessao, operador, TOMADA)
