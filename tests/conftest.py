import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta

import pytest

from cfauto.core import clock


class RelogioFixo:
    def __init__(self, inicio: datetime) -> None:
        self.atual = inicio

    def agora(self) -> datetime:
        return self.atual

    def avancar(self, **delta: float) -> None:
        self.atual += timedelta(**delta)

    def definir(self, quando: datetime) -> None:
        self.atual = quando


@pytest.fixture
def relogio():
    r = RelogioFixo(datetime(2026, 9, 23, 10, 0, 0))
    clock.definir(r.agora)
    yield r
    clock.resetar()


@pytest.fixture
def engine(tmp_path):
    from cfauto.core.db import criar_engine
    from cfauto.core.migracoes import migrar

    eng = criar_engine(f"sqlite:///{tmp_path / 'teste.db'}")
    migrar(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def fabrica(engine):
    from cfauto.core.db import criar_fabrica

    return criar_fabrica(engine)


@pytest.fixture
def sessao(fabrica):
    from cfauto.core.db import transacao

    with transacao(fabrica) as s:
        yield s


@pytest.fixture
def admin(sessao, relogio):
    from cfauto.auth.service import NovoUsuario, criar_usuario

    return criar_usuario(
        sessao, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
    )


@pytest.fixture
def operador(sessao, admin):
    from cfauto.auth.service import NovoUsuario, criar_usuario
    from cfauto.core.permissoes import Modulo

    return criar_usuario(
        sessao,
        admin,
        NovoUsuario(
            nome="Maria",
            login="maria",
            senha="segredo2",
            modulos=frozenset({Modulo.PDV, Modulo.CLIENTES}),
        ),
    )
