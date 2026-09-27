from dataclasses import dataclass
from enum import StrEnum

from cfauto.core.errors import PermissaoNegada


class Modulo(StrEnum):
    PDV = "PDV"
    ESTOQUE = "ESTOQUE"
    CLIENTES = "CLIENTES"
    SAIDAS = "SAIDAS"
    COMPRAS = "COMPRAS"
    HISTORICO = "HISTORICO"
    CFAUTO = "CFAUTO"
    USUARIOS = "USUARIOS"


TITULOS: dict[Modulo, str] = {
    Modulo.PDV: "PDV / Caixa",
    Modulo.ESTOQUE: "Estoque",
    Modulo.CLIENTES: "Clientes",
    Modulo.SAIDAS: "Saídas",
    Modulo.COMPRAS: "Compras",
    Modulo.HISTORICO: "Histórico",
    Modulo.CFAUTO: "CFAUTO",
    Modulo.USUARIOS: "Usuários",
}

# Nunca liberados por lista de módulos: só o flag admin dá acesso.
MODULOS_SO_ADMIN: frozenset[Modulo] = frozenset({Modulo.CFAUTO, Modulo.USUARIOS})


@dataclass(frozen=True)
class Ator:
    """Usuário autenticado, passado a todos os serviços."""

    id: int
    nome: str
    login: str
    admin: bool
    modulos: frozenset[Modulo]


def tem_modulo(ator: Ator, modulo: Modulo) -> bool:
    if modulo in MODULOS_SO_ADMIN:
        return ator.admin
    return ator.admin or modulo in ator.modulos


def exigir_modulo(ator: Ator, modulo: Modulo) -> None:
    if not tem_modulo(ator, modulo):
        raise PermissaoNegada(f"Sem acesso ao módulo {modulo.value}.")


def exigir_admin(ator: Ator) -> None:
    if not ator.admin:
        raise PermissaoNegada("Ação restrita a administradores.")
