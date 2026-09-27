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
    texto = valor.strip().replace("\u00a0", "").replace(" ", "")
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


MILESIMO = Decimal("0.001")
DECIMO_DE_MILESIMO = Decimal("0.0001")


def arredondar_qtd(valor: Decimal) -> Decimal:
    return valor.quantize(MILESIMO, rounding=ROUND_HALF_UP)


def arredondar_custo(valor: Decimal) -> Decimal:
    return valor.quantize(DECIMO_DE_MILESIMO, rounding=ROUND_HALF_UP)


def formatar_qtd(valor: Decimal) -> str:
    """Quantidade para exibição: 1.500 → '1,5'; 1234 → '1.234'."""
    v = arredondar_qtd(valor)
    sinal = "-" if v < 0 else ""
    inteiro, _, fracao = f"{abs(v):.3f}".partition(".")
    grupos = f"{int(inteiro):,}".replace(",", ".")
    fracao = fracao.rstrip("0")
    return f"{sinal}{grupos},{fracao}" if fracao else f"{sinal}{grupos}"


def formatar_pct(fracao: Decimal) -> str:
    """Fração como porcentagem com 1 casa: 0.125 → '12,5%'."""
    pct = (fracao * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{pct:.1f}".replace(".", ",") + "%"


def formatar_numero(valor: Decimal, casas_minimas: int = 2) -> str:
    """Decimal para campo editável, sem separador de milhar: 1234.5 → '1234,50'."""
    inteiro, _, fracao = format(valor, "f").partition(".")
    fracao = fracao.rstrip("0").ljust(casas_minimas, "0")
    return f"{inteiro},{fracao}" if fracao else inteiro
