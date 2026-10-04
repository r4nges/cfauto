"""Sessão de caixa: abertura com fundo de troco, painel ao vivo e fechamento com sangria."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.auth.models import Usuario
from cfauto.caixa.calculo import calcular_sangria, resumir, resumo_para_json
from cfauto.caixa.models import SessaoCaixa, StatusSessao, Venda
from cfauto.caixa.schemas import FechamentoSessao, MovimentoResumo, PainelSessao, ResumoSessao
from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import SessaoFechada, SessaoJaAberta, ValorInvalido
from cfauto.core.money import arredondar
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo


def nome_usuario(s: Session, usuario_id: int | None) -> str | None:
    """Nome do usuário, ou None se o id for None ou o usuário não existir."""
    if usuario_id is None:
        return None
    usuario = s.get(Usuario, usuario_id)
    return None if usuario is None else usuario.nome


def carregar_sessao_aberta(s: Session) -> SessaoCaixa | None:
    return s.scalar(select(SessaoCaixa).where(SessaoCaixa.status == StatusSessao.ABERTA))


def exigir_sessao_aberta(s: Session) -> SessaoCaixa:
    sessao = carregar_sessao_aberta(s)
    if sessao is None:
        raise SessaoFechada("Caixa fechado: abra o caixa antes de continuar.")
    return sessao


def resumo_da_sessao(s: Session, sessao: SessaoCaixa) -> ResumoSessao:
    vendas = s.scalars(select(Venda).where(Venda.sessao_id == sessao.id).order_by(Venda.id))
    return resumir(
        sessao.fundo_troco,
        [
            MovimentoResumo(
                tipo=v.tipo,
                forma=v.forma_pagamento,
                bruto=v.bruto,
                taxa=v.taxa,
                liquido=v.liquido,
                repasse=v.repasse_taxa,
                cancelada=v.cancelada,
            )
            for v in vendas
        ],
    )


def _painel(s: Session, sessao: SessaoCaixa) -> PainelSessao:
    resumo = resumo_da_sessao(s, sessao)
    return PainelSessao(
        id=sessao.id,
        protocolo=sessao.protocolo,
        aberta_em=sessao.aberta_em,
        aberta_por=nome_usuario(s, sessao.aberta_por) or "",
        fundo_troco=sessao.fundo_troco,
        gaveta=resumo.gaveta,
        qtd_vendas=sum(totais.qtd for totais in resumo.vendas.values()),
    )


def _gerar_protocolo(s: Session, agora: datetime) -> str:
    """CX-yyyyMMdd-HHmm; aberturas no mesmo minuto ganham sufixo -2, -3…"""
    base = f"CX-{agora:%Y%m%d-%H%M}"
    usados = set(
        s.scalars(select(SessaoCaixa.protocolo).where(SessaoCaixa.protocolo.startswith(base)))
    )
    if base not in usados:
        return base
    numero = 2
    while f"{base}-{numero}" in usados:
        numero += 1
    return f"{base}-{numero}"


def sessao_aberta(s: Session, ator: Ator) -> PainelSessao | None:
    exigir_modulo(ator, Modulo.PDV)
    sessao = carregar_sessao_aberta(s)
    return None if sessao is None else _painel(s, sessao)


def sugestao_fundo(s: Session, ator: Ator) -> Decimal:
    """Valor mantido na gaveta no último fechamento; 0 se nunca houve fechamento."""
    exigir_modulo(ator, Modulo.PDV)
    ultima = s.scalar(
        select(SessaoCaixa)
        .where(SessaoCaixa.status == StatusSessao.FECHADA)
        .order_by(SessaoCaixa.fechada_em.desc(), SessaoCaixa.id.desc())
        .limit(1)
    )
    if ultima is None or ultima.valor_mantido is None:
        return Decimal("0.00")
    return ultima.valor_mantido


def abrir_sessao(s: Session, ator: Ator, fundo_troco: Decimal) -> PainelSessao:
    exigir_modulo(ator, Modulo.PDV)
    fundo = arredondar(fundo_troco)
    if fundo < 0:
        raise ValorInvalido("O fundo de troco não pode ser negativo.")
    if carregar_sessao_aberta(s) is not None:
        raise SessaoJaAberta("Já existe um caixa aberto; feche-o antes de abrir outro.")
    agora = clock.agora()
    sessao = SessaoCaixa(
        protocolo=_gerar_protocolo(s, agora),
        status=StatusSessao.ABERTA,
        aberta_em=agora,
        aberta_por=ator.id,
        fundo_troco=fundo,
    )
    s.add(sessao)
    s.flush()
    registrar(
        s,
        ator.id,
        "abrir",
        "sessao_caixa",
        sessao.id,
        None,
        {"protocolo": sessao.protocolo, "fundo_troco": fundo, "status": sessao.status},
    )
    return _painel(s, sessao)


def previa_fechamento(s: Session, ator: Ator) -> ResumoSessao:
    exigir_modulo(ator, Modulo.PDV)
    return resumo_da_sessao(s, exigir_sessao_aberta(s))


def fechar_sessao(s: Session, ator: Ator, valor_mantido: Decimal) -> FechamentoSessao:
    """Grava o resumo e a sangria; a sessão fechada fica imutável."""
    exigir_modulo(ator, Modulo.PDV)
    sessao = exigir_sessao_aberta(s)
    resumo = resumo_da_sessao(s, sessao)
    mantido = arredondar(valor_mantido)
    sangria = arredondar(calcular_sangria(resumo.gaveta, mantido))
    sessao.status = StatusSessao.FECHADA
    sessao.fechada_em = clock.agora()
    sessao.fechada_por = ator.id
    sessao.valor_mantido = mantido
    sessao.sangria = sangria
    sessao.resumo_json = resumo_para_json(resumo)
    s.flush()
    registrar(
        s,
        ator.id,
        "fechar",
        "sessao_caixa",
        sessao.id,
        {"status": StatusSessao.ABERTA},
        {
            "status": sessao.status,
            "gaveta": resumo.gaveta,
            "total_vendido": resumo.total_vendido,
            "valor_mantido": mantido,
            "sangria": sangria,
        },
    )
    return FechamentoSessao(
        protocolo=sessao.protocolo, resumo=resumo, valor_mantido=mantido, sangria=sangria
    )
