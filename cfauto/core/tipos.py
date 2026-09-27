"""Tipos de coluna: Decimal como inteiro escalado (soma exata no SQLite) e enum como texto."""

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Dialect, Integer, String
from sqlalchemy.types import TypeDecorator


class DecimalEscalado(TypeDecorator[Decimal]):
    impl = Integer
    cache_ok = True

    def __init__(self, casas: int) -> None:
        super().__init__()
        self.casas = casas
        self._fator = Decimal(10) ** casas
        self._quantum = Decimal(1).scaleb(-casas)

    def process_bind_param(self, value: Any, dialect: Dialect) -> int | None:
        if value is None:
            return None
        if isinstance(value, float | bool):
            raise TypeError(f"Use Decimal, não float: {value!r}")
        escalado = Decimal(value) * self._fator
        return int(escalado.to_integral_value(rounding=ROUND_HALF_UP))

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return (Decimal(value) / self._fator).quantize(self._quantum)


class EnumTexto[E: StrEnum](TypeDecorator[E]):
    """StrEnum guardado pelo valor (VARCHAR); volta do banco como o próprio enum."""

    impl = String
    cache_ok = True

    def __init__(self, enum: type[E], tamanho: int = 20) -> None:
        super().__init__(tamanho)
        self.enum = enum

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return self.enum(value).value

    def process_result_value(self, value: Any, dialect: Dialect) -> E | None:
        if value is None:
            return None
        return self.enum(value)


def Dinheiro() -> DecimalEscalado:  # noqa: N802 - usado como tipo de coluna
    return DecimalEscalado(2)


def Custo() -> DecimalEscalado:  # noqa: N802 - usado como tipo de coluna
    """Custo unitário: 4 casas (R$ 0,035 não pode virar R$ 0,04)."""
    return DecimalEscalado(4)


def Quantidade() -> DecimalEscalado:  # noqa: N802 - usado como tipo de coluna
    return DecimalEscalado(3)
