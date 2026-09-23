"""Criação/migração do banco local e backups."""

import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from cfauto.auth.service import existe_usuario
from cfauto.core import clock
from cfauto.core.db import criar_engine, criar_fabrica, transacao
from cfauto.core.migracoes import migracoes_pendentes, migrar

log = logging.getLogger("cfauto.sistema")


@dataclass(frozen=True)
class Caminhos:
    base: Path

    @property
    def db(self) -> Path:
        return self.base / "cfauto.db"

    @property
    def backups(self) -> Path:
        return self.base / "backups"

    @property
    def logs(self) -> Path:
        return self.base / "logs"


def caminhos_padrao() -> Caminhos:
    home = os.environ.get("CFAUTO_HOME")
    if home:
        return Caminhos(Path(home))
    appdata = os.environ.get("APPDATA")
    return Caminhos((Path(appdata) if appdata else Path.home()) / "CFAUTO")


def fazer_backup(db: Path, destino: Path, manter: int = 7) -> Path | None:
    if not db.exists():
        return None
    destino.mkdir(parents=True, exist_ok=True)
    alvo = destino / f"cfauto-{clock.agora():%Y%m%d-%H%M%S}.db"
    contador = 1
    while alvo.exists():
        alvo = destino / f"cfauto-{clock.agora():%Y%m%d-%H%M%S}-{contador}.db"
        contador += 1
    origem = sqlite3.connect(db)
    copia = sqlite3.connect(alvo)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    for antigo in sorted(destino.glob("cfauto-*.db"))[:-manter]:
        antigo.unlink()
    log.info("backup criado em %s", alvo)
    return alvo


@dataclass
class Ambiente:
    caminhos: Caminhos
    engine: Engine
    fabrica: sessionmaker[Session]
    primeira_execucao: bool


def inicializar(caminhos: Caminhos) -> Ambiente:
    caminhos.base.mkdir(parents=True, exist_ok=True)
    existia = caminhos.db.exists()
    engine = criar_engine(f"sqlite:///{caminhos.db}")
    if existia and migracoes_pendentes(engine):
        fazer_backup(caminhos.db, caminhos.backups)
    migrar(engine)
    fabrica = criar_fabrica(engine)
    with transacao(fabrica) as s:
        primeira = not existe_usuario(s)
    return Ambiente(caminhos, engine, fabrica, primeira)
