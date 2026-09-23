from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from cfauto.core import clock
from cfauto.core.jsonutil import para_json
from cfauto.core.models import AuditLog


def registrar(
    s: Session,
    usuario_id: int | None,
    acao: str,
    entidade: str,
    entidade_id: object | None,
    antes: Mapping[str, Any] | None = None,
    depois: Mapping[str, Any] | None = None,
) -> AuditLog:
    registro = AuditLog(
        timestamp=clock.agora(),
        usuario_id=usuario_id,
        acao=acao,
        entidade=entidade,
        entidade_id=None if entidade_id is None else str(entidade_id),
        antes=None if antes is None else para_json(antes),
        depois=None if depois is None else para_json(depois),
    )
    s.add(registro)
    s.flush()
    return registro
