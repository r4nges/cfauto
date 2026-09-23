from collections.abc import Sequence
from contextlib import suppress

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session, sessionmaker

from cfauto.jobs.modelo import Job
from cfauto.jobs.runner import rodar


class Agendador:
    def __init__(self, fabrica: sessionmaker[Session], jobs: Sequence[Job]) -> None:
        self._fabrica = fabrica
        self._jobs = list(jobs)
        self._scheduler = BackgroundScheduler()

    def _executar(self, job: Job) -> None:
        # rodar() registra a falha no log; a thread do agendador não pode morrer.
        with suppress(Exception):
            rodar(self._fabrica, job)

    def iniciar(self) -> None:
        for job in self._jobs:
            self._scheduler.add_job(
                self._executar,
                CronTrigger(**job.cron),
                args=[job],
                id=job.nome,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=3600,
            )
        self._scheduler.start()

    def nomes_agendados(self) -> list[str]:
        return [j.id for j in self._scheduler.get_jobs()]

    def parar(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
