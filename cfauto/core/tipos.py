"""Decimal armazenado como inteiro escalado: soma exata no SQLite."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Dialect, Integer
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


def Dinheiro() -> DecimalEscalado:  # noqa: N802 - usado como tipo de coluna
    return DecimalEscalado(2)


def Quantidade() -> DecimalEscalado:  # noqa: N802 - usado como tipo de coluna
    return DecimalEscalado(3)
