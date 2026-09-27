"""Painel CFAUTO: Bens Físicos (Ativo Não Circulante do Balancete)."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from cfauto.core.db import Base, ComTimestamps
from cfauto.core.tipos import Dinheiro, EnumTexto


class TipoBem(StrEnum):
    MOVEL = "MOVEL"
    INTANGIVEL = "INTANGIVEL"
    OUTROS = "OUTROS"


TITULOS_TIPO_BEM: dict[TipoBem, str] = {
    TipoBem.MOVEL: "Móvel",
    TipoBem.INTANGIVEL: "Intangível",
    TipoBem.OUTROS: "Outros",
}


class BemFisico(ComTimestamps, Base):
    __tablename__ = "bem_fisico"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    descricao: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[TipoBem] = mapped_column(EnumTexto(TipoBem))
    valor: Mapped[Decimal] = mapped_column(Dinheiro())
    data_cadastro: Mapped[date]
    # Baixado = False: sai do Balancete.
    ativo: Mapped[bool] = mapped_column(default=True)
