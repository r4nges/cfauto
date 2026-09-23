from datetime import datetime

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from cfauto.core.db import Base, ComTimestamps


class Usuario(ComTimestamps, Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    funcao: Mapped[str] = mapped_column(String(60), default="")
    login: Mapped[str] = mapped_column(String(60), unique=True)
    senha_hash: Mapped[str | None] = mapped_column(String(255))
    hash_legado: Mapped[str | None] = mapped_column(String(64))
    admin: Mapped[bool] = mapped_column(default=False)
    # Lista de valores de Modulo. Sempre reatribuir a lista inteira (não mutar).
    modulos: Mapped[list[str]] = mapped_column(JSON, default=list)
    tentativas_falhas: Mapped[int] = mapped_column(default=0)
    bloqueado_ate: Mapped[datetime | None]
    ativo: Mapped[bool] = mapped_column(default=True)
