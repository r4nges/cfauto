import logging
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from cfauto.core import clock, config
from cfauto.core.db import transacao
from cfauto.jobs.modelo import Job

log = logging.getLogger("cfauto.jobs")


def _chave(nome: str) -> str:
    return f"job.{nome}.ultima_execucao"


def ultima_execucao(fabrica: sessionmaker[Session], nome: str) -> datetime | None:
    with transacao(fabrica) as s:
        valor = config.obter(s, _chave(nome))
    return None if valor is None else datetime.fromisoformat(valor)


def rodar(fabrica: sessionmaker[Session], job: Job) -> None:
    log.info("job %s iniciado", job.nome)
    try:
        job.executar()
        with transacao(fabrica) as s:
            config.definir(s, _chave(job.nome), clock.agora())
    except Exception:
        # cobre falha em executar() OU na gravação de última execução: nos dois
        # casos a exceção é logada e relançada, e a última execução não é gravada.
        log.exception("job %s falhou", job.nome)
        raise
    log.info("job %s concluído", job.nome)


def catchup(fabrica: sessionmaker[Session], jobs: Iterable[Job]) -> dict[str, Exception | None]:
    resultado: dict[str, Exception | None] = {}
    agora = clock.agora()
    for job in jobs:
        if not job.precisa_catchup(ultima_execucao(fabrica, job.nome), agora):
            continue
        try:
            rodar(fabrica, job)
            resultado[job.nome] = None
        except Exception as erro:  # já registrado em log por rodar()
            resultado[job.nome] = erro
    return resultado
