"""Clientes: cadastro, dependentes e razão (livro) de lançamentos do saldo devedor."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cfauto.core.db import Base, ComTimestamps
from cfauto.core.tipos import DecimalEscalado, Dinheiro, EnumTexto

LIMITE_PADRAO = Decimal("500.00")
MAX_DEPENDENTES = 4


class Sexo(StrEnum):
    M = "M"
    F = "F"
    OUTRO = "OUTRO"


TITULOS_SEXO: dict[Sexo, str] = {Sexo.M: "Masculino", Sexo.F: "Feminino", Sexo.OUTRO: "Outro"}


class FrequenciaJuros(StrEnum):
    DIARIO = "DIARIO"
    MENSAL = "MENSAL"
    BIMESTRAL = "BIMESTRAL"


TITULOS_FREQUENCIA: dict[FrequenciaJuros, str] = {
    FrequenciaJuros.DIARIO: "Diária",
    FrequenciaJuros.MENSAL: "Mensal",
    FrequenciaJuros.BIMESTRAL: "Bimestral",
}


class TipoLancamento(StrEnum):
    DEBITO = "DEBITO"  # aumenta a dívida
    CREDITO = "CREDITO"  # abate a dívida


class MotivoLancamento(StrEnum):
    COMPRA_ANOTADA = "COMPRA_ANOTADA"
    PAGAMENTO = "PAGAMENTO"
    CORRECAO = "CORRECAO"
    OUTRO = "OUTRO"


TITULOS_MOTIVO_LANCAMENTO: dict[MotivoLancamento, str] = {
    MotivoLancamento.COMPRA_ANOTADA: "Compra anotada",
    MotivoLancamento.PAGAMENTO: "Pagamento",
    MotivoLancamento.CORRECAO: "Correção",
    MotivoLancamento.OUTRO: "Outro",
}


class Cliente(ComTimestamps, Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    nome_busca: Mapped[str] = mapped_column(String(120), index=True)
    celular: Mapped[str] = mapped_column(String(11), index=True)
    cpf: Mapped[str | None] = mapped_column(String(11), index=True)
    email: Mapped[str | None] = mapped_column(String(120))
    endereco: Mapped[str] = mapped_column(String(200), default="")
    nascimento: Mapped[date | None]
    sexo: Mapped[Sexo | None] = mapped_column(EnumTexto(Sexo))
    observacoes: Mapped[str] = mapped_column(String(500), default="")
    # Nulo = sem limite.
    limite: Mapped[Decimal | None] = mapped_column(Dinheiro())
    # Só muda por razao.lancar(); negativo = crédito a favor do cliente.
    saldo_devedor: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    somente_titular: Mapped[bool] = mapped_column(default=False)
    # Guardados sem efeito, como no original.
    aumento_auto: Mapped[bool] = mapped_column(default=False)
    aumento_auto_pct: Mapped[Decimal] = mapped_column(DecimalEscalado(2), default=Decimal(5))
    juros_dias: Mapped[int] = mapped_column(default=30)
    juros_frequencia: Mapped[FrequenciaJuros] = mapped_column(
        EnumTexto(FrequenciaJuros), default=FrequenciaJuros.MENSAL
    )
    juros_pct: Mapped[Decimal] = mapped_column(DecimalEscalado(2), default=Decimal(2))
    juros_mora: Mapped[bool] = mapped_column(default=False)
    ativo: Mapped[bool] = mapped_column(default=True)
    dependentes: Mapped[list["ClienteDependente"]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
        order_by="ClienteDependente.id",
        lazy="selectin",
    )

    @property
    def disponivel(self) -> Decimal | None:
        """None = ilimitado. Pode passar do limite (crédito a favor) ou ficar negativo."""
        return None if self.limite is None else self.limite - self.saldo_devedor


class ClienteDependente(ComTimestamps, Base):
    __tablename__ = "cliente_dependente"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    parentesco: Mapped[str] = mapped_column(String(40), default="")
    cliente: Mapped[Cliente] = relationship(back_populates="dependentes")


class ClienteLancamento(ComTimestamps, Base):
    """Livro do saldo devedor: só inserção, nunca alterado nem apagado."""

    __tablename__ = "cliente_lancamento"
    __table_args__ = (Index("ix_cliente_lancamento_cliente_data", "cliente_id", "data_hora"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    data_hora: Mapped[datetime]
    tipo: Mapped[TipoLancamento] = mapped_column(EnumTexto(TipoLancamento))
    valor: Mapped[Decimal] = mapped_column(Dinheiro())
    saldo_apos: Mapped[Decimal] = mapped_column(Dinheiro())
    motivo: Mapped[MotivoLancamento] = mapped_column(EnumTexto(MotivoLancamento))
    observacao: Mapped[str] = mapped_column(String(200), default="")
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
