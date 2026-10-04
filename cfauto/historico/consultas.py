"""Histórico: consulta das vendas e das sessões de caixa já fechadas (só leitura)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.caixa.calculo import descrever_venda, resumo_de_json
from cfauto.caixa.models import FormaPagamento, SessaoCaixa, StatusSessao, TipoVenda, Venda
from cfauto.caixa.schemas import ResumoSessao
from cfauto.caixa.sessao import nome_usuario
from cfauto.clientes.models import Cliente
from cfauto.core.errors import RegistroNaoEncontrado, ValorInvalido
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo


@dataclass(frozen=True)
class FiltroHistorico:
    inicio: date
    fim: date
    forma: FormaPagamento | None = None
    tipo: TipoVenda | None = None
    cliente_id: int | None = None
    incluir_canceladas: bool = False


@dataclass(frozen=True)
class LinhaHistorico:
    venda_id: int
    protocolo: str
    data_hora: datetime
    descricao: str
    cliente: str | None
    tipo: TipoVenda
    forma: FormaPagamento
    bruto: Decimal
    taxa: Decimal
    liquido: Decimal
    dias_liquidacao: int | None
    cancelada: bool


@dataclass(frozen=True)
class ItemDetalhe:
    descricao: str
    categoria: str
    qtd: Decimal
    preco_unit: Decimal
    subtotal: Decimal


@dataclass(frozen=True)
class DetalheVenda:
    linha: LinhaHistorico
    itens: tuple[ItemDetalhe, ...]
    desconto: Decimal
    usuario: str
    autorizado_por: str | None
    cancelada_por: str | None
    cancelamento_autorizado_por: str | None
    motivo_cancelamento: str | None


@dataclass(frozen=True)
class LinhaSessao:
    id: int
    protocolo: str
    aberta_em: datetime
    fechada_em: datetime
    aberta_por: str
    fechada_por: str
    resumo: ResumoSessao
    valor_mantido: Decimal
    sangria: Decimal


def _intervalo(inicio: date, fim: date) -> tuple[datetime, datetime]:
    """[inicio 00:00, dia seguinte a fim 00:00)."""
    if fim < inicio:
        raise ValorInvalido("A data final é anterior à inicial.")
    return datetime.combine(inicio, time.min), datetime.combine(fim + timedelta(days=1), time.min)


def _linha(s: Session, venda: Venda, protocolo: str) -> LinhaHistorico:
    cliente = None if venda.cliente_id is None else s.get(Cliente, venda.cliente_id)
    dias = (
        None
        if venda.data_liquidacao is None
        else (venda.data_liquidacao - venda.data_hora.date()).days
    )
    return LinhaHistorico(
        venda_id=venda.id,
        protocolo=protocolo,
        data_hora=venda.data_hora,
        descricao=descrever_venda(venda.tipo, [i.descricao_snapshot for i in venda.itens]),
        cliente=None if cliente is None else cliente.nome,
        tipo=venda.tipo,
        forma=venda.forma_pagamento,
        bruto=venda.bruto,
        taxa=venda.taxa,
        liquido=venda.liquido,
        dias_liquidacao=dias,
        cancelada=venda.cancelada,
    )


def listar_vendas(s: Session, ator: Ator, filtro: FiltroHistorico) -> list[LinhaHistorico]:
    """Vendas e recebimentos de sessões FECHADAS no período, mais recentes primeiro."""
    exigir_modulo(ator, Modulo.HISTORICO)
    de, ate = _intervalo(filtro.inicio, filtro.fim)
    consulta = (
        select(Venda, SessaoCaixa.protocolo)
        .join(SessaoCaixa, Venda.sessao_id == SessaoCaixa.id)
        .where(
            SessaoCaixa.status == StatusSessao.FECHADA,
            Venda.data_hora >= de,
            Venda.data_hora < ate,
        )
        .order_by(Venda.data_hora.desc(), Venda.id.desc())
    )
    if filtro.forma is not None:
        consulta = consulta.where(Venda.forma_pagamento == filtro.forma)
    if filtro.tipo is not None:
        consulta = consulta.where(Venda.tipo == filtro.tipo)
    if filtro.cliente_id is not None:
        consulta = consulta.where(Venda.cliente_id == filtro.cliente_id)
    if not filtro.incluir_canceladas:
        consulta = consulta.where(Venda.cancelada.is_(False))
    return [_linha(s, linha.Venda, linha.protocolo) for linha in s.execute(consulta).all()]


def detalhe_venda(s: Session, ator: Ator, venda_id: int) -> DetalheVenda:
    exigir_modulo(ator, Modulo.HISTORICO)
    venda = s.get(Venda, venda_id)
    sessao = None if venda is None else s.get(SessaoCaixa, venda.sessao_id)
    if venda is None or sessao is None or sessao.status != StatusSessao.FECHADA:
        raise RegistroNaoEncontrado("Venda não encontrada no Histórico.")
    return DetalheVenda(
        linha=_linha(s, venda, sessao.protocolo),
        itens=tuple(
            ItemDetalhe(
                descricao=i.descricao_snapshot,
                categoria=i.categoria_snapshot,
                qtd=i.qtd,
                preco_unit=i.preco_unit,
                subtotal=i.subtotal,
            )
            for i in venda.itens
        ),
        desconto=venda.desconto,
        usuario=nome_usuario(s, venda.usuario_id) or "",
        autorizado_por=nome_usuario(s, venda.autorizado_por),
        cancelada_por=nome_usuario(s, venda.cancelada_por),
        cancelamento_autorizado_por=nome_usuario(s, venda.cancelamento_autorizado_por),
        motivo_cancelamento=venda.motivo_cancelamento,
    )


def _linha_sessao(s: Session, sessao: SessaoCaixa) -> LinhaSessao:
    if (
        sessao.fechada_em is None
        or sessao.fechada_por is None
        or sessao.valor_mantido is None
        or sessao.sangria is None
        or sessao.resumo_json is None
    ):
        raise RegistroNaoEncontrado(f"Sessão {sessao.protocolo} sem dados de fechamento.")
    return LinhaSessao(
        id=sessao.id,
        protocolo=sessao.protocolo,
        aberta_em=sessao.aberta_em,
        fechada_em=sessao.fechada_em,
        aberta_por=nome_usuario(s, sessao.aberta_por) or "",
        fechada_por=nome_usuario(s, sessao.fechada_por) or "",
        resumo=resumo_de_json(sessao.resumo_json),
        valor_mantido=sessao.valor_mantido,
        sangria=sessao.sangria,
    )


def listar_sessoes(s: Session, ator: Ator, inicio: date, fim: date) -> list[LinhaSessao]:
    """Sessões FECHADAS com fechamento no período, mais recentes primeiro."""
    exigir_modulo(ator, Modulo.HISTORICO)
    de, ate = _intervalo(inicio, fim)
    sessoes = s.scalars(
        select(SessaoCaixa)
        .where(
            SessaoCaixa.status == StatusSessao.FECHADA,
            SessaoCaixa.fechada_em >= de,
            SessaoCaixa.fechada_em < ate,
        )
        .order_by(SessaoCaixa.fechada_em.desc(), SessaoCaixa.id.desc())
    )
    return [_linha_sessao(s, sessao) for sessao in sessoes]
