"""Cálculos do caixa: funções puras (sem banco nem ORM), usadas pela prévia da UI e pelos
serviços — as duas pontas chegam sempre ao mesmo número."""

from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from cfauto.caixa.models import DESCRICAO_RECEBIMENTO, TITULOS_FORMA, FormaPagamento, TipoVenda
from cfauto.caixa.schemas import (
    Desconto,
    MovimentoResumo,
    Pagamento,
    ResumoSessao,
    TaxaForma,
    TipoDesconto,
    TotaisForma,
)
from cfauto.core.errors import ValorInvalido
from cfauto.core.jsonutil import para_json
from cfauto.core.money import arredondar, arredondar_qtd, formatar_brl

ZERO = Decimal("0.00")
CEM = Decimal(100)


def preco_de_venda(preco_venda: Decimal, preco_promocional: Decimal | None) -> Decimal:
    """Preço praticado no caixa: promocional quando informado (mesmo que 0 seja inválido na
    origem), senão o de venda."""
    return preco_promocional if preco_promocional is not None else preco_venda


def subtotal_item(qtd: Decimal, preco_unit: Decimal) -> Decimal:
    return arredondar(arredondar_qtd(qtd) * preco_unit)


def valor_desconto(subtotal: Decimal, desconto: Desconto) -> Decimal:
    """Desconto em R$ (0 até o subtotal) ou em % (0 a 100, sobre o subtotal)."""
    if desconto.tipo == TipoDesconto.PERCENTUAL:
        if desconto.valor < 0 or desconto.valor > CEM:
            raise ValorInvalido("Desconto em %: informe de 0 a 100.")
        return arredondar(subtotal * desconto.valor / CEM)
    valor = arredondar(desconto.valor)
    if valor < 0 or valor > subtotal:
        raise ValorInvalido(
            f"Desconto em R$: informe de R$ 0,00 até o subtotal ({formatar_brl(subtotal)})."
        )
    return valor


def valor_cobrado(bruto: Decimal, taxa: Decimal, repasse: bool) -> Decimal:
    """O que o cliente paga: com repasse, a taxa vai para ele."""
    return bruto + taxa if repasse else bruto


def calcular_pagamento(
    bruto: Decimal, forma: FormaPagamento, taxa: TaxaForma | None, data: date
) -> Pagamento:
    """Taxa arredondada no total da venda; crediário não tem taxa nem liquidação."""
    if forma == FormaPagamento.CREDIARIO:
        return Pagamento(
            taxa=ZERO, liquido=bruto, cobrado=bruto, repasse=False, data_liquidacao=None
        )
    if taxa is None:
        raise ValorInvalido(f"Taxa não configurada para {TITULOS_FORMA[forma]}.")
    valor_taxa = arredondar(bruto * taxa.pct / CEM)
    return Pagamento(
        taxa=valor_taxa,
        liquido=bruto if taxa.repasse else bruto - valor_taxa,
        cobrado=valor_cobrado(bruto, valor_taxa, taxa.repasse),
        repasse=taxa.repasse,
        data_liquidacao=data + timedelta(days=taxa.dias),
    )


def troco(cobrado: Decimal, recebido: Decimal) -> Decimal:
    if recebido < cobrado:
        raise ValorInvalido("Valor recebido menor que o total.")
    return arredondar(recebido - cobrado)


def _totalizar(
    grupos: dict[FormaPagamento, list[MovimentoResumo]],
) -> dict[FormaPagamento, TotaisForma]:
    totais: dict[FormaPagamento, TotaisForma] = {}
    for forma in FormaPagamento:
        movimentos = grupos.get(forma)
        if not movimentos:
            continue
        totais[forma] = TotaisForma(
            qtd=len(movimentos),
            bruto=sum((m.bruto for m in movimentos), ZERO),
            taxa=sum((m.taxa for m in movimentos), ZERO),
            liquido=sum((m.liquido for m in movimentos), ZERO),
            cobrado=sum((valor_cobrado(m.bruto, m.taxa, m.repasse) for m in movimentos), ZERO),
        )
    return totais


def resumir(fundo_troco: Decimal, movimentos: Iterable[MovimentoResumo]) -> ResumoSessao:
    """Resumo por forma; recebimentos em linhas próprias (divergência nº 32); canceladas só
    contadas. Gaveta = fundo + tudo cobrado em dinheiro."""
    vendas: dict[FormaPagamento, list[MovimentoResumo]] = {}
    recebimentos: dict[FormaPagamento, list[MovimentoResumo]] = {}
    canceladas_qtd = 0
    canceladas_bruto = ZERO
    for m in movimentos:
        if m.cancelada:
            canceladas_qtd += 1
            canceladas_bruto += m.bruto
            continue
        destino = vendas if m.tipo == TipoVenda.VENDA else recebimentos
        destino.setdefault(m.forma, []).append(m)
    totais_vendas = _totalizar(vendas)
    totais_recebimentos = _totalizar(recebimentos)
    dinheiro = sum(
        (
            totais[FormaPagamento.DINHEIRO].cobrado
            for totais in (totais_vendas, totais_recebimentos)
            if FormaPagamento.DINHEIRO in totais
        ),
        ZERO,
    )
    return ResumoSessao(
        fundo_troco=fundo_troco,
        vendas=totais_vendas,
        recebimentos=totais_recebimentos,
        canceladas_qtd=canceladas_qtd,
        canceladas_bruto=canceladas_bruto,
        total_vendido=sum((t.bruto for t in totais_vendas.values()), ZERO),
        dinheiro=dinheiro,
        gaveta=fundo_troco + dinheiro,
    )


def calcular_sangria(gaveta: Decimal, valor_mantido: Decimal) -> Decimal:
    mantido = arredondar(valor_mantido)
    if mantido < 0:
        raise ValorInvalido("O valor mantido no caixa não pode ser negativo.")
    if mantido > gaveta:
        raise ValorInvalido(
            f"O valor mantido não pode passar do total da gaveta ({formatar_brl(gaveta)})."
        )
    return gaveta - mantido


def descrever_venda(tipo: TipoVenda, descricoes: Sequence[str]) -> str:
    if tipo == TipoVenda.RECEBIMENTO:
        return DESCRICAO_RECEBIMENTO
    if not descricoes:
        return ""
    resto = len(descricoes) - 1
    if resto == 0:
        return descricoes[0]
    return f"{descricoes[0]} (+{resto} {'item' if resto == 1 else 'itens'})"


def _totais_para_json(totais: dict[FormaPagamento, TotaisForma]) -> dict[str, Any]:
    return {
        forma.value: {
            "qtd": t.qtd,
            "bruto": t.bruto,
            "taxa": t.taxa,
            "liquido": t.liquido,
            "cobrado": t.cobrado,
        }
        for forma, t in totais.items()
    }


def resumo_para_json(resumo: ResumoSessao) -> dict[str, Any]:
    """Decimais viram texto (core.jsonutil.para_json); volta por resumo_de_json."""
    dados: dict[str, Any] = para_json(
        {
            "fundo_troco": resumo.fundo_troco,
            "vendas": _totais_para_json(resumo.vendas),
            "recebimentos": _totais_para_json(resumo.recebimentos),
            "canceladas_qtd": resumo.canceladas_qtd,
            "canceladas_bruto": resumo.canceladas_bruto,
            "total_vendido": resumo.total_vendido,
            "dinheiro": resumo.dinheiro,
            "gaveta": resumo.gaveta,
        }
    )
    return dados


def _totais_de_json(dados: dict[str, Any]) -> dict[FormaPagamento, TotaisForma]:
    totais: dict[FormaPagamento, TotaisForma] = {}
    for forma in FormaPagamento:
        t = dados.get(forma.value)
        if t is None:
            continue
        totais[forma] = TotaisForma(
            qtd=int(t["qtd"]),
            bruto=Decimal(t["bruto"]),
            taxa=Decimal(t["taxa"]),
            liquido=Decimal(t["liquido"]),
            cobrado=Decimal(t["cobrado"]),
        )
    return totais


def resumo_de_json(dados: dict[str, Any]) -> ResumoSessao:
    return ResumoSessao(
        fundo_troco=Decimal(dados["fundo_troco"]),
        vendas=_totais_de_json(dados["vendas"]),
        recebimentos=_totais_de_json(dados["recebimentos"]),
        canceladas_qtd=int(dados["canceladas_qtd"]),
        canceladas_bruto=Decimal(dados["canceladas_bruto"]),
        total_vendido=Decimal(dados["total_vendido"]),
        dinheiro=Decimal(dados["dinheiro"]),
        gaveta=Decimal(dados["gaveta"]),
    )
