from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.auth.models import Usuario
from cfauto.core.models import AuditLog
from cfauto.core.permissoes import Ator, exigir_admin


@dataclass(frozen=True)
class RegistroAuditoria:
    timestamp: datetime
    usuario_nome: str | None
    acao: str
    entidade: str
    entidade_id: str | None
    antes: dict[str, Any] | None
    depois: dict[str, Any] | None


def consultar(
    s: Session,
    ator: Ator,
    *,
    entidade: str | None = None,
    usuario_id: int | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    limite: int = 500,
) -> list[RegistroAuditoria]:
    exigir_admin(ator)
    consulta = select(AuditLog, Usuario.nome.label("usuario_nome")).outerjoin(
        Usuario, AuditLog.usuario_id == Usuario.id
    )
    if entidade:
        consulta = consulta.where(AuditLog.entidade == entidade)
    if usuario_id is not None:
        consulta = consulta.where(AuditLog.usuario_id == usuario_id)
    if desde is not None:
        consulta = consulta.where(AuditLog.timestamp >= desde)
    if ate is not None:
        consulta = consulta.where(AuditLog.timestamp <= ate)
    consulta = consulta.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(limite)
    return [
        RegistroAuditoria(
            timestamp=row.AuditLog.timestamp,
            usuario_nome=row.usuario_nome,
            acao=row.AuditLog.acao,
            entidade=row.AuditLog.entidade,
            entidade_id=row.AuditLog.entidade_id,
            antes=row.AuditLog.antes,
            depois=row.AuditLog.depois,
        )
        for row in s.execute(consulta).all()
    ]
