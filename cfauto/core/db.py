"""Infra de banco: Base declarativa, engine SQLite, fábrica de sessões e transação."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from cfauto.core import clock

CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO_NOMES)


def _agora() -> datetime:
    return clock.agora()


class ComTimestamps:
    criado_em: Mapped[datetime] = mapped_column(default=_agora)
    atualizado_em: Mapped[datetime] = mapped_column(default=_agora, onupdate=_agora)


def criar_engine(url: str) -> Engine:
    engine = create_engine(url)
    em_memoria = ":memory:" in url

    @event.listens_for(engine, "connect")
    def _pragmas(conexao: Any, _registro: Any) -> None:
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        if not em_memoria:
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def criar_fabrica(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transacao(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    sessao = fabrica()
    try:
        yield sessao
        sessao.commit()
    except BaseException:
        sessao.rollback()
        raise
    finally:
        sessao.close()
