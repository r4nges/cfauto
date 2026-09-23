from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.auth.auditoria import consultar
from cfauto.auth.models import Usuario
from cfauto.core import config
from cfauto.core.audit import registrar
from cfauto.core.errors import PermissaoNegada
from cfauto.core.models import AuditLog
from cfauto.core.permissoes import Ator


@pytest.fixture
def dono(sessao):
    u = Usuario(nome="Dono", login="dono", senha_hash="x", admin=True, modulos=[])
    sessao.add(u)
    sessao.flush()
    return Ator(u.id, u.nome, u.login, True, frozenset())


def test_registrar_serializa_valores(sessao, relogio, dono):
    reg = registrar(
        sessao,
        dono.id,
        "alterar",
        "produto",
        7,
        antes={"preco": Decimal("1.50")},
        depois={"preco": Decimal("2.00")},
    )
    assert reg.timestamp == datetime(2026, 9, 23, 10, 0)
    assert reg.entidade_id == "7"
    assert reg.antes == {"preco": "1.50"}
    assert reg.depois == {"preco": "2.00"}


def test_config_obter_padrao_e_definir(sessao):
    assert config.obter(sessao, "empresa.nome", "—") == "—"
    config.definir(sessao, "empresa.nome", "Loja X")
    assert config.obter(sessao, "empresa.nome") == "Loja X"
    config.definir(sessao, "taxa", Decimal("1.5"))
    assert config.obter(sessao, "taxa") == "1.5"


def test_config_auditada(sessao, dono):
    config.definir(sessao, "capital_social", Decimal("1000"), ator=dono, auditar=True)
    config.definir(sessao, "capital_social", Decimal("2000"), ator=dono, auditar=True)
    regs = sessao.scalars(select(AuditLog).where(AuditLog.entidade == "config")).all()
    assert [(r.antes, r.depois) for r in regs] == [
        ({"valor": None}, {"valor": "1000"}),
        ({"valor": "1000"}, {"valor": "2000"}),
    ]


def test_consultar_auditoria(sessao, relogio, dono):
    registrar(sessao, dono.id, "criar", "produto", 1)
    relogio.avancar(minutes=1)
    registrar(sessao, None, "instalar", "licenca", "Loja")
    todos = consultar(sessao, dono)
    assert [r.entidade for r in todos] == ["licenca", "produto"]
    assert todos[1].usuario_nome == "Dono"
    assert todos[0].usuario_nome is None
    assert [r.entidade for r in consultar(sessao, dono, entidade="produto")] == ["produto"]
    desde = datetime(2026, 9, 23, 10, 0, 30)
    assert [r.entidade for r in consultar(sessao, dono, desde=desde)] == ["licenca"]


def test_consultar_auditoria_so_admin(sessao):
    operador = Ator(99, "Op", "op", False, frozenset())
    with pytest.raises(PermissaoNegada):
        consultar(sessao, operador)
