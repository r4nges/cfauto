"""Dinheiro sempre em Decimal. Parser aceita formato brasileiro."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from cfauto.core.errors import ValorInvalido

CENTAVO = Decimal("0.01")
_MILHAR_BR = re.compile(r"^\d{1,3}(\.\d{3})+$")


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def para_decimal(valor: str | int | float | Decimal) -> Decimal:
    if isinstance(valor, bool):
        raise ValorInvalido(f"Valor inválido: {valor!r}")
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, float):
        return Decimal(str(valor))
    texto = valor.strip().replace(" ", "").replace(" ", "")
    negativo = texto.startswith("-")
    if negativo:
        texto = texto[1:]
    texto = texto.replace("R$", "")
    if not texto:
        raise ValorInvalido("Valor vazio.")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif _MILHAR_BR.match(texto):
        texto = texto.replace(".", "")
    try:
        resultado = Decimal(texto)
    except InvalidOperation as erro:
        raise ValorInvalido(f"Valor inválido: {valor!r}") from erro
    if not resultado.is_finite():
        raise ValorInvalido(f"Valor inválido: {valor!r}")
    return -resultado if negativo else resultado


def formatar_brl(valor: Decimal) -> str:
    v = arredondar(valor)
    sinal = "-" if v < 0 else ""
    inteiro, _, centavos = f"{abs(v):.2f}".partition(".")
    grupos = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {grupos},{centavos}"
