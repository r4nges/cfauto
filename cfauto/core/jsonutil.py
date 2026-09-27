"""Conversão de valores de domínio para JSON (auditoria, config)."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


def para_json(valor: Any) -> Any:
    if valor is None or isinstance(valor, bool | int | str):
        return valor
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, float):
        return str(Decimal(str(valor)))
    if isinstance(valor, Mapping):
        return {str(k): para_json(v) for k, v in valor.items()}
    if isinstance(valor, set | frozenset):
        return sorted(para_json(v) for v in valor)
    if isinstance(valor, list | tuple):
        return [para_json(v) for v in valor]
    raise TypeError(f"Tipo não serializável: {type(valor).__name__}")
