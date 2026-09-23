from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.permissoes import Ator
from cfauto.ui.comum import PaginaEmConstrucao


class TelaAuditoria(PaginaEmConstrucao):
    def __init__(self, fabrica: sessionmaker[Session], ator: Ator) -> None:
        super().__init__("Auditoria")
