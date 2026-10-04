"""Entradas e saídas do caixa, com tipos reais (a UI não recebe entidade ORM)."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from cfauto.caixa.models import FormaPagamento, TipoVenda


class TipoDesconto(StrEnum):
    REAIS = "REAIS"
    PERCENTUAL = "PERCENTUAL"


@dataclass(frozen=True)
class Desconto:
    tipo: TipoDesconto = TipoDesconto.REAIS
    valor: Decimal = Decimal(0)


@dataclass(frozen=True)
class ItemVenda:
    """Exatamente um de produto_id / servico_id."""

    qtd: Decimal
    produto_id: int | None = None
    servico_id: int | None = None


@dataclass(frozen=True)
class NovaVenda:
    itens: tuple[ItemVenda, ...]
    forma: FormaPagamento
    desconto: Desconto = Desconto()
    cliente_id: int | None = None


@dataclass(frozen=True)
class TaxaForma:
    forma: FormaPagamento
    pct: Decimal
    dias: int
    repasse: bool


@dataclass(frozen=True)
class Pagamento:
    taxa: Decimal
    liquido: Decimal
    cobrado: Decimal
    repasse: bool
    data_liquidacao: date | None


@dataclass(frozen=True)
class MovimentoResumo:
    """O que o resumo da sessão precisa de cada venda/recebimento."""

    tipo: TipoVenda
    forma: FormaPagamento
    bruto: Decimal
    taxa: Decimal
    liquido: Decimal
    repasse: bool
    cancelada: bool


@dataclass(frozen=True)
class TotaisForma:
    qtd: int
    bruto: Decimal
    taxa: Decimal
    liquido: Decimal
    cobrado: Decimal


@dataclass(frozen=True)
class ResumoSessao:
    fundo_troco: Decimal
    # Só formas com movimento, na ordem de FormaPagamento.
    vendas: dict[FormaPagamento, TotaisForma]
    recebimentos: dict[FormaPagamento, TotaisForma]
    canceladas_qtd: int
    canceladas_bruto: Decimal
    # Σ bruto das VENDAS não canceladas (inclui crediário, não inclui recebimentos).
    total_vendido: Decimal
    # Σ cobrado em DINHEIRO (vendas + recebimentos).
    dinheiro: Decimal
    # fundo_troco + dinheiro
    gaveta: Decimal


@dataclass(frozen=True)
class PainelSessao:
    id: int
    protocolo: str
    aberta_em: datetime
    aberta_por: str
    fundo_troco: Decimal
    gaveta: Decimal
    qtd_vendas: int


@dataclass(frozen=True)
class FechamentoSessao:
    protocolo: str
    resumo: ResumoSessao
    valor_mantido: Decimal
    sangria: Decimal


@dataclass(frozen=True)
class LinhaVenda:
    id: int
    data_hora: datetime
    tipo: TipoVenda
    forma: FormaPagamento
    cliente: str | None
    descricao: str
    bruto: Decimal
    taxa: Decimal
    liquido: Decimal
    cobrado: Decimal
    usuario: str
    cancelada: bool
