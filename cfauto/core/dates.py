"""Normalização de datas na borda (UI, importador, XML, APIs)."""

from contextlib import suppress
from datetime import date, datetime

from cfauto.core.errors import DataInvalida

_FORMATOS_DATA = ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")
_FORMATOS_DATAHORA = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
)


def para_datahora(valor: date | datetime | str) -> datetime:
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in _FORMATOS_DATAHORA + _FORMATOS_DATA:
            try:
                return datetime.strptime(texto, formato)
            except ValueError:
                continue
        # ISO 8601 com fuso (XML da NF-e: 2026-09-20T10:15:00-03:00): vale a hora de parede.
        with suppress(ValueError):
            return datetime.fromisoformat(texto).replace(tzinfo=None)
    raise DataInvalida(f"Data inválida: {valor!r}")


def para_data(valor: date | datetime | str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return para_datahora(valor).date()
