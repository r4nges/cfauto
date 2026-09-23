from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

import cfauto.modelos  # noqa: F401
from cfauto.core.db import Base, criar_engine
from cfauto.core.migracoes import migracoes_pendentes, migrar


def test_migrar_cria_tabelas(engine):
    tabelas = set(inspect(engine).get_table_names())
    assert {"usuario", "audit_log", "config_item", "licenca_estado"} <= tabelas


def test_sem_pendencias_apos_migrar(engine):
    assert migracoes_pendentes(engine) is False


def test_banco_novo_tem_pendencias(tmp_path):
    engine = criar_engine(f"sqlite:///{tmp_path / 'novo.db'}")
    assert migracoes_pendentes(engine) is True
    migrar(engine)
    assert migracoes_pendentes(engine) is False
    engine.dispose()


def test_modelos_batem_com_migracoes(engine):
    with engine.connect() as conexao:
        contexto = MigrationContext.configure(conexao, opts={"compare_type": True})
        diferencas = compare_metadata(contexto, Base.metadata)
    assert diferencas == []
