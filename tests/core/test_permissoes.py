import pytest

from cfauto.core.errors import PermissaoNegada
from cfauto.core.permissoes import (
    Ator,
    Modulo,
    exigir_admin,
    exigir_algum_modulo,
    exigir_modulo,
    tem_modulo,
)

OPERADOR = Ator(1, "Maria", "maria", False, frozenset({Modulo.PDV, Modulo.CLIENTES}))
ADMIN = Ator(2, "João", "joao", True, frozenset())


def test_operador_so_tem_seus_modulos():
    assert tem_modulo(OPERADOR, Modulo.PDV)
    assert not tem_modulo(OPERADOR, Modulo.CFAUTO)


def test_admin_tem_tudo():
    assert all(tem_modulo(ADMIN, m) for m in Modulo)


def test_exigir_modulo_nega():
    with pytest.raises(PermissaoNegada, match="CFAUTO"):
        exigir_modulo(OPERADOR, Modulo.CFAUTO)
    exigir_modulo(OPERADOR, Modulo.PDV)


def test_exigir_admin():
    with pytest.raises(PermissaoNegada):
        exigir_admin(OPERADOR)
    exigir_admin(ADMIN)


def test_modulos_so_admin_ignoram_lista_do_operador():
    operador = Ator(3, "Ana", "ana", False, frozenset({Modulo.CFAUTO, Modulo.USUARIOS}))
    assert not tem_modulo(operador, Modulo.CFAUTO)
    assert not tem_modulo(operador, Modulo.USUARIOS)
    with pytest.raises(PermissaoNegada):
        exigir_modulo(operador, Modulo.CFAUTO)


def test_exigir_algum_modulo():
    exigir_algum_modulo(OPERADOR, Modulo.ESTOQUE, Modulo.PDV)
    exigir_algum_modulo(ADMIN, Modulo.ESTOQUE)
    with pytest.raises(PermissaoNegada, match="ESTOQUE ou COMPRAS"):
        exigir_algum_modulo(OPERADOR, Modulo.ESTOQUE, Modulo.COMPRAS)
