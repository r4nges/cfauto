"""Execução programática do Alembic (funciona também empacotado pelo PyInstaller)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

PASTA_MIGRACOES = Path(__file__).parent.parent / "migrations"


def _config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(PASTA_MIGRACOES))
    return cfg


def migrar(engine: Engine) -> None:
    cfg = _config()
    with engine.begin() as conexao:
        cfg.attributes["connection"] = conexao
        command.upgrade(cfg, "head")


def migracoes_pendentes(engine: Engine) -> bool:
    heads = set(ScriptDirectory.from_config(_config()).get_heads())
    with engine.connect() as conexao:
        atuais = set(MigrationContext.configure(conexao).get_current_heads())
    return atuais != heads
