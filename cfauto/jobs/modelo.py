from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

RegraCatchup = Callable[[datetime | None, datetime], bool]


@dataclass(frozen=True)
class Job:
    nome: str
    executar: Callable[[], None]
    cron: dict[str, Any]  # argumentos do CronTrigger do APScheduler
    precisa_catchup: RegraCatchup


def diario(ultima: datetime | None, agora: datetime) -> bool:
    return ultima is None or ultima.date() < agora.date()


def a_cada(intervalo: timedelta) -> RegraCatchup:
    def regra(ultima: datetime | None, agora: datetime) -> bool:
        return ultima is None or agora - ultima >= intervalo

    return regra
