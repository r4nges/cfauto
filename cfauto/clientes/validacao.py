"""Validação e formatação dos dados de cliente (funções puras, sem banco)."""

import re
from decimal import Decimal

from cfauto.core.errors import ValorInvalido
from cfauto.core.money import formatar_brl

TAMANHO_NOME = 120
TAMANHO_EMAIL = 120
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def so_digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isascii() and c.isdigit())


def normalizar_nome(texto: str) -> str:
    nome = " ".join(texto.split())
    if len(nome.split()) < 2:
        raise ValorInvalido("Informe nome e sobrenome.")
    if len(nome) > TAMANHO_NOME:
        raise ValorInvalido(f"Nome: máximo de {TAMANHO_NOME} caracteres.")
    return nome


def normalizar_celular(texto: str) -> str:
    """Celular com DDD, só dígitos (10 ou 11). Aceita o prefixo +55."""
    digitos = so_digitos(texto)
    if not digitos:
        raise ValorInvalido("Celular obrigatório.")
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        raise ValorInvalido("Celular deve ter DDD + número (10 ou 11 dígitos).")
    if int(digitos[:2]) < 11:
        raise ValorInvalido("DDD inválido.")
    return digitos


def cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or not (digitos.isascii() and digitos.isdigit()):
        return False
    if len(set(digitos)) == 1:
        return False
    for tamanho in (9, 10):
        pesos = range(tamanho + 1, 1, -1)
        soma = sum(int(d) * peso for d, peso in zip(digitos[:tamanho], pesos, strict=True))
        if (soma * 10) % 11 % 10 != int(digitos[tamanho]):
            return False
    return True


def normalizar_cpf(texto: str) -> str | None:
    """Vazio (ou só pontuação de máscara) → None; senão 11 dígitos com DV válido."""
    if not texto.strip(" .-"):
        return None
    digitos = so_digitos(texto)
    if not cpf_valido(digitos):
        raise ValorInvalido("CPF inválido.")
    return digitos


def normalizar_email(texto: str) -> str | None:
    email = texto.strip()
    if not email:
        return None
    if len(email) > TAMANHO_EMAIL or not _EMAIL.match(email):
        raise ValorInvalido("E-mail inválido.")
    return email


def formatar_celular(digitos: str) -> str:
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return digitos


def formatar_cpf(digitos: str | None) -> str:
    if not digitos:
        return ""
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def formatar_saldo(saldo: Decimal) -> str:
    """Saldo devedor para exibição; negativo é crédito a favor do cliente."""
    if saldo < 0:
        return f"Crédito a favor {formatar_brl(-saldo)}"
    return formatar_brl(saldo)
