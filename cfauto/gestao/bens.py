"""Bens Físicos: Ativo Não Circulante do Balancete. Só admin (módulo CFAUTO)."""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import RegistroNaoEncontrado, ValorInvalido
from cfauto.core.money import arredondar
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo
from cfauto.core.sequencias import proximo_codigo
from cfauto.gestao.models import BemFisico
from cfauto.gestao.schemas import DadosBem


def _snapshot(bem: BemFisico) -> dict[str, Any]:
    return {
        "codigo": bem.codigo,
        "descricao": bem.descricao,
        "tipo": bem.tipo,
        "valor": bem.valor,
        "data_cadastro": bem.data_cadastro,
        "ativo": bem.ativo,
    }


def _validar(dados: DadosBem) -> tuple[str, Decimal]:
    descricao = dados.descricao.strip()
    if not descricao:
        raise ValorInvalido("Descrição obrigatória.")
    valor = arredondar(dados.valor)
    if valor <= 0:
        raise ValorInvalido("O valor deve ser maior que zero.")
    return descricao, valor


def _obter(s: Session, bem_id: int) -> BemFisico:
    bem = s.get(BemFisico, bem_id)
    if bem is None:
        raise RegistroNaoEncontrado("Bem não encontrado.")
    return bem


def criar_bem(s: Session, ator: Ator, dados: DadosBem) -> BemFisico:
    exigir_modulo(ator, Modulo.CFAUTO)
    descricao, valor = _validar(dados)
    bem = BemFisico(
        codigo=proximo_codigo(s, "bem", prefixo="BEM-", digitos=3),
        descricao=descricao,
        tipo=dados.tipo,
        valor=valor,
        data_cadastro=dados.data_cadastro or clock.hoje(),
        ativo=True,
    )
    s.add(bem)
    s.flush()
    registrar(s, ator.id, "criar", "bem_fisico", bem.id, None, _snapshot(bem))
    return bem


def atualizar_bem(s: Session, ator: Ator, bem_id: int, dados: DadosBem) -> BemFisico:
    exigir_modulo(ator, Modulo.CFAUTO)
    bem = _obter(s, bem_id)
    descricao, valor = _validar(dados)
    antes = _snapshot(bem)
    bem.descricao = descricao
    bem.tipo = dados.tipo
    bem.valor = valor
    if dados.data_cadastro is not None:
        bem.data_cadastro = dados.data_cadastro
    s.flush()
    registrar(s, ator.id, "alterar", "bem_fisico", bem.id, antes, _snapshot(bem))
    return bem


def _definir_ativo(s: Session, ator: Ator, bem_id: int, ativo: bool, acao: str) -> BemFisico:
    exigir_modulo(ator, Modulo.CFAUTO)
    bem = _obter(s, bem_id)
    if bem.ativo == ativo:
        raise ValorInvalido("O bem já está ativo." if ativo else "O bem já está baixado.")
    bem.ativo = ativo
    s.flush()
    registrar(s, ator.id, acao, "bem_fisico", bem.id, {"ativo": not ativo}, {"ativo": ativo})
    return bem


def baixar_bem(s: Session, ator: Ator, bem_id: int) -> BemFisico:
    return _definir_ativo(s, ator, bem_id, False, "baixar")


def reativar_bem(s: Session, ator: Ator, bem_id: int) -> BemFisico:
    return _definir_ativo(s, ator, bem_id, True, "reativar")


def listar_bens(s: Session, ator: Ator, *, incluir_baixados: bool = False) -> list[BemFisico]:
    exigir_modulo(ator, Modulo.CFAUTO)
    consulta = select(BemFisico).order_by(BemFisico.id)
    if not incluir_baixados:
        consulta = consulta.where(BemFisico.ativo.is_(True))
    return list(s.scalars(consulta))


def total_bens_ativos(s: Session, ator: Ator) -> Decimal:
    """Σ valor dos bens ativos (Ativo Não Circulante do Balancete)."""
    exigir_modulo(ator, Modulo.CFAUTO)
    total = s.scalar(select(func.sum(BemFisico.valor)).where(BemFisico.ativo.is_(True)))
    return total if total is not None else Decimal("0.00")
