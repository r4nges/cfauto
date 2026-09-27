from datetime import date, datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from cfauto.core.db import Base, _agora


class LicencaEstado(Base):
    """Linha única (id=1) com a chave instalada e a última data vista."""

    __tablename__ = "licenca_estado"

    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str | None] = mapped_column(Text)
    ultima_data_vista: Mapped[date | None]
    atualizado_em: Mapped[datetime] = mapped_column(default=_agora, onupdate=_agora)
