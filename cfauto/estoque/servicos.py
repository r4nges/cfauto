"""Serviço: preço = materiais × (1 + mão de obra %). Nunca movimenta estoque."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.core.audit import registrar
from cfauto.core.errors import RegistroNaoEncontrado, ValorInvalido
from cfauto.core.money import arredondar, arredondar_custo, arredondar_qtd
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo
from cfauto.core.sequencias import proximo_codigo
from cfauto.core.texto import normalizar_texto
from cfauto.estoque.models import Servico, ServicoMaterial
from cfauto.estoque.schemas import DadosServico


def _snapshot(servico: Servico) -> dict[str, Any]:
    return {
        "codigo": servico.codigo,
        "nome": servico.nome,
        "mao_obra_pct": servico.mao_obra_pct,
        "materiais": [
            {"descricao": m.descricao, "custo_unit": m.custo_unit, "qtd": m.qtd}
            for m in servico.materiais
        ],
        "preco": servico.preco,
        "ativo": servico.ativo,
    }


def _validar(dados: DadosServico) -> tuple[str, list[ServicoMaterial]]:
    nome = dados.nome.strip()
    if not nome:
        raise ValorInvalido("Nome do serviço obrigatório.")
    if dados.mao_obra_pct < 0:
        raise ValorInvalido("Mão de obra não pode ser negativa.")
    if not dados.materiais:
        raise ValorInvalido("Informe ao menos um material.")
    materiais = []
    for numero, material in enumerate(dados.materiais, start=1):
        descricao = material.descricao.strip()
        if not descricao:
            raise ValorInvalido(f"Material {numero}: descrição obrigatória.")
        custo = arredondar_custo(material.custo_unit)
        if custo <= 0:
            raise ValorInvalido(f"Material {numero}: custo deve ser maior que zero.")
        qtd = arredondar_qtd(material.qtd)
        if qtd <= 0:
            raise ValorInvalido(f"Material {numero}: quantidade deve ser maior que zero.")
        materiais.append(ServicoMaterial(descricao=descricao, custo_unit=custo, qtd=qtd))
    return nome, materiais


def _obter(s: Session, servico_id: int) -> Servico:
    servico = s.get(Servico, servico_id)
    if servico is None:
        raise RegistroNaoEncontrado("Serviço não encontrado.")
    return servico


def criar_servico(s: Session, ator: Ator, dados: DadosServico) -> Servico:
    exigir_modulo(ator, Modulo.ESTOQUE)
    nome, materiais = _validar(dados)
    servico = Servico(
        codigo=proximo_codigo(s, "servico", prefixo="SERV-", digitos=3),
        nome=nome,
        mao_obra_pct=arredondar(dados.mao_obra_pct),
        ativo=True,
        materiais=materiais,
    )
    s.add(servico)
    s.flush()
    registrar(s, ator.id, "criar", "servico", servico.id, None, _snapshot(servico))
    return servico


def atualizar_servico(s: Session, ator: Ator, servico_id: int, dados: DadosServico) -> Servico:
    """Substitui nome, mão de obra e a lista inteira de materiais."""
    exigir_modulo(ator, Modulo.ESTOQUE)
    servico = _obter(s, servico_id)
    nome, materiais = _validar(dados)
    antes = _snapshot(servico)
    servico.nome = nome
    servico.mao_obra_pct = arredondar(dados.mao_obra_pct)
    servico.materiais = materiais
    s.flush()
    registrar(s, ator.id, "alterar", "servico", servico.id, antes, _snapshot(servico))
    return servico


def _definir_ativo(s: Session, ator: Ator, servico_id: int, ativo: bool, acao: str) -> Servico:
    exigir_modulo(ator, Modulo.ESTOQUE)
    servico = _obter(s, servico_id)
    if servico.ativo == ativo:
        raise ValorInvalido("O serviço já está ativo." if ativo else "O serviço já está inativo.")
    servico.ativo = ativo
    s.flush()
    registrar(s, ator.id, acao, "servico", servico.id, {"ativo": not ativo}, {"ativo": ativo})
    return servico


def desativar_servico(s: Session, ator: Ator, servico_id: int) -> Servico:
    return _definir_ativo(s, ator, servico_id, False, "desativar")


def reativar_servico(s: Session, ator: Ator, servico_id: int) -> Servico:
    return _definir_ativo(s, ator, servico_id, True, "reativar")


def listar_servicos(s: Session, ator: Ator, *, incluir_inativos: bool = False) -> list[Servico]:
    exigir_modulo(ator, Modulo.ESTOQUE)
    consulta = select(Servico)
    if not incluir_inativos:
        consulta = consulta.where(Servico.ativo.is_(True))
    return sorted(s.scalars(consulta), key=lambda sv: (normalizar_texto(sv.nome), sv.id))
