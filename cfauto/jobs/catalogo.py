from cfauto.jobs.modelo import Job, diario
from cfauto.sistema.provisionamento import Ambiente, fazer_backup


def jobs_padrao(ambiente: Ambiente) -> list[Job]:
    caminhos = ambiente.caminhos

    def backup() -> None:
        fazer_backup(caminhos.db, caminhos.backups)

    return [
        Job(
            nome="backup",
            executar=backup,
            cron={"hour": 12, "minute": 30},
            precisa_catchup=diario,
        ),
    ]
