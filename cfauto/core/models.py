from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from cfauto.core.db import Base, _agora


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    acao: Mapped[str] = mapped_column(String(40))
    entidade: Mapped[str] = mapped_column(String(60), index=True)
    entidade_id: Mapped[str | None] = mapped_column(String(60))
    antes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    depois: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ConfigItem(Base):
    __tablename__ = "config_item"

    chave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[Any] = mapped_column(JSON, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(default=_agora, onupdate=_agora)
