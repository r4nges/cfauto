"""Taxas por forma de pagamento: lidas pelo PDV, alteradas só pelo admin."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.caixa.models import FORMAS_COM_TAXA, TITULOS_FORMA, FormaPagamento, TaxaPagamento
from cfauto.caixa.schemas import TaxaForma
from cfauto.core.audit import registrar
from cfauto.core.errors import ValorInvalido
from cfauto.core.money import arredondar
from cfauto.core.permissoes import Ator, Modulo, exigir_admin, exigir_modulo

PCT_MAXIMO = Decimal(100)
DIAS_MAXIMO = 365


def _para_schema(taxa: TaxaPagamento) -> TaxaForma:
    return TaxaForma(forma=taxa.forma, pct=taxa.pct, dias=taxa.dias, repasse=taxa.repasse)


def _carregar(s: Session, forma: FormaPagamento) -> TaxaPagamento | None:
    return s.scalar(select(TaxaPagamento).where(TaxaPagamento.forma == forma))


def listar_taxas(s: Session, ator: Ator) -> list[TaxaForma]:
    exigir_modulo(ator, Modulo.PDV)
    por_forma = {t.forma: t for t in s.scalars(select(TaxaPagamento))}
    return [_para_schema(por_forma[f]) for f in FORMAS_COM_TAXA if f in por_forma]


def taxa_da_forma(s: Session, forma: FormaPagamento) -> TaxaForma | None:
    """Uso interno dos serviços (sem checar permissão). Crediário não tem taxa."""
    if forma not in FORMAS_COM_TAXA:
        return None
    taxa = _carregar(s, forma)
    return None if taxa is None else _para_schema(taxa)


def atualizar_taxa(
    s: Session, ator: Ator, forma: FormaPagamento, pct: Decimal, dias: int, repasse: bool
) -> TaxaForma:
    exigir_admin(ator)
    if forma not in FORMAS_COM_TAXA:
        raise ValorInvalido(f"{TITULOS_FORMA[forma]} não tem taxa configurável.")
    pct = arredondar(pct)
    if pct < 0:
        raise ValorInvalido("A taxa não pode ser negativa.")
    if pct > PCT_MAXIMO:
        raise ValorInvalido("A taxa não pode passar de 100%.")
    if dias < 0:
        raise ValorInvalido("Os dias até a liquidação não podem ser negativos.")
    if dias > DIAS_MAXIMO:
        raise ValorInvalido(f"Os dias até a liquidação não podem passar de {DIAS_MAXIMO}.")
    taxa = _carregar(s, forma)
    if taxa is None:
        antes = None
        taxa = TaxaPagamento(forma=forma, pct=pct, dias=dias, repasse=repasse)
        s.add(taxa)
    else:
        antes = {"pct": taxa.pct, "dias": taxa.dias, "repasse": taxa.repasse}
        taxa.pct = pct
        taxa.dias = dias
        taxa.repasse = repasse
    s.flush()
    registrar(
        s,
        ator.id,
        "alterar",
        "taxa_pagamento",
        forma.value,
        antes,
        {"pct": pct, "dias": dias, "repasse": repasse},
    )
    return _para_schema(taxa)
