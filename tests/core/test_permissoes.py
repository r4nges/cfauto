import pytest

from cfauto.core.errors import PermissaoNegada
from cfauto.core.permissoes import Ator, Modulo, exigir_admin, exigir_modulo, tem_modulo

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
