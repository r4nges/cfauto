"""Caixa: sessão, venda (com itens) e taxas por forma de pagamento."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cfauto.core.db import Base, ComTimestamps
from cfauto.core.tipos import DecimalEscalado, Dinheiro, EnumTexto, Quantidade


class StatusSessao(StrEnum):
    ABERTA = "ABERTA"
    FECHADA = "FECHADA"


class TipoVenda(StrEnum):
    VENDA = "VENDA"
    RECEBIMENTO = "RECEBIMENTO"


class FormaPagamento(StrEnum):
    DINHEIRO = "DINHEIRO"
    PIX = "PIX"
    DEBITO = "DEBITO"
    CREDITO = "CREDITO"
    CREDIARIO = "CREDIARIO"


TITULOS_FORMA: dict[FormaPagamento, str] = {
    FormaPagamento.DINHEIRO: "Dinheiro",
    FormaPagamento.PIX: "PIX",
    FormaPagamento.DEBITO: "Débito",
    FormaPagamento.CREDITO: "Crédito",
    FormaPagamento.CREDIARIO: "Crediário",
}

TITULOS_TIPO_VENDA: dict[TipoVenda, str] = {
    TipoVenda.VENDA: "Venda",
    TipoVenda.RECEBIMENTO: "Recebimento",
}

# Formas com linha em taxa_pagamento e aceitas no recebimento de crediário.
FORMAS_COM_TAXA: tuple[FormaPagamento, ...] = (
    FormaPagamento.DINHEIRO,
    FormaPagamento.PIX,
    FormaPagamento.DEBITO,
    FormaPagamento.CREDITO,
)

DESCRICAO_RECEBIMENTO = "RECEBIMENTO DE CONTA / FIADO"
CATEGORIA_SERVICO = "Serviço"
TAMANHO_MOTIVO_CANCELAMENTO = 200


class SessaoCaixa(ComTimestamps, Base):
    __tablename__ = "sessao_caixa"
    __table_args__ = (
        # No máximo uma sessão aberta: o próprio banco garante.
        Index(
            "ix_sessao_caixa_aberta",
            "status",
            unique=True,
            sqlite_where=text("status = 'ABERTA'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    protocolo: Mapped[str] = mapped_column(String(24), unique=True)
    status: Mapped[StatusSessao] = mapped_column(EnumTexto(StatusSessao))
    aberta_em: Mapped[datetime]
    aberta_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    fundo_troco: Mapped[Decimal] = mapped_column(Dinheiro())
    fechada_em: Mapped[datetime | None]
    fechada_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    valor_mantido: Mapped[Decimal | None] = mapped_column(Dinheiro())
    sangria: Mapped[Decimal | None] = mapped_column(Dinheiro())
    resumo_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Venda(ComTimestamps, Base):
    """Venda ou recebimento de crediário (recebimento não tem itens). Nunca é apagada."""

    __tablename__ = "venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    sessao_id: Mapped[int] = mapped_column(ForeignKey("sessao_caixa.id"), index=True)
    data_hora: Mapped[datetime] = mapped_column(index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    # Admin que autorizou vender com estoque insuficiente.
    autorizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"), index=True)
    tipo: Mapped[TipoVenda] = mapped_column(EnumTexto(TipoVenda))
    forma_pagamento: Mapped[FormaPagamento] = mapped_column(EnumTexto(FormaPagamento))
    desconto: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    # Já com o desconto; valor cobrado = bruto + taxa com repasse (derivado, não gravado).
    bruto: Mapped[Decimal] = mapped_column(Dinheiro())
    taxa: Mapped[Decimal] = mapped_column(Dinheiro())
    liquido: Mapped[Decimal] = mapped_column(Dinheiro())
    repasse_taxa: Mapped[bool] = mapped_column(default=False)
    # Nula no crediário ("aguardando pagamento").
    data_liquidacao: Mapped[date | None]
    cancelada: Mapped[bool] = mapped_column(default=False)
    cancelada_em: Mapped[datetime | None]
    cancelada_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    cancelamento_autorizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(TAMANHO_MOTIVO_CANCELAMENTO))
    sessao: Mapped[SessaoCaixa] = relationship(lazy="selectin")
    itens: Mapped[list["VendaItem"]] = relationship(
        back_populates="venda",
        cascade="all, delete-orphan",
        order_by="VendaItem.id",
        lazy="selectin",
    )


class VendaItem(ComTimestamps, Base):
    __tablename__ = "venda_item"
    __table_args__ = (
        CheckConstraint("(produto_id IS NULL) <> (servico_id IS NULL)", name="produto_xor_servico"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(ForeignKey("venda.id"), index=True)
    produto_id: Mapped[int | None] = mapped_column(ForeignKey("produto.id"), index=True)
    servico_id: Mapped[int | None] = mapped_column(ForeignKey("servico.id"))
    descricao_snapshot: Mapped[str] = mapped_column(String(200))
    categoria_snapshot: Mapped[str] = mapped_column(String(60))
    qtd: Mapped[Decimal] = mapped_column(Quantidade())
    preco_unit: Mapped[Decimal] = mapped_column(Dinheiro())
    subtotal: Mapped[Decimal] = mapped_column(Dinheiro())
    venda: Mapped[Venda] = relationship(back_populates="itens")


class TaxaPagamento(ComTimestamps, Base):
    """Taxa e prazo de liquidação por forma. 0 é valor válido (bug nº 4 do original)."""

    __tablename__ = "taxa_pagamento"

    id: Mapped[int] = mapped_column(primary_key=True)
    forma: Mapped[FormaPagamento] = mapped_column(EnumTexto(FormaPagamento), unique=True)
    pct: Mapped[Decimal] = mapped_column(DecimalEscalado(2))
    dias: Mapped[int]
    repasse: Mapped[bool] = mapped_column(default=False)
