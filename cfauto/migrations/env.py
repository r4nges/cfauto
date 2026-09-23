from alembic import context
from sqlalchemy import engine_from_config, pool

import cfauto.modelos  # noqa: F401
from cfauto.core.db import Base

config = context.config
target_metadata = Base.metadata


def _rodar(conexao) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=conexao,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    conexao = config.attributes.get("connection")
    if conexao is not None:
        _rodar(conexao)
        return
    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as nova:
        _rodar(nova)


if context.is_offline_mode():
    raise RuntimeError("Modo offline do Alembic não é suportado.")
rodar_online()
