from PySide6.QtWidgets import QTabWidget, QWidget
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.permissoes import TITULOS, Ator, Modulo
from cfauto.ui.auditoria import TelaAuditoria
from cfauto.ui.gestao.pagina import PaginaGestao
from cfauto.ui.parametros import PaginaParametros
from cfauto.ui.usuarios import TelaUsuarios


class PaginaConfiguracoes(QTabWidget):
    """Seção só-admin: módulos administrativos e a parametrização do sistema."""

    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.addTab(PaginaGestao(fabrica, ator), TITULOS[Modulo.CFAUTO])
        self.addTab(TelaUsuarios(fabrica, ator), TITULOS[Modulo.USUARIOS])
        self.addTab(TelaAuditoria(fabrica, ator), "Auditoria")
        self.addTab(PaginaParametros(fabrica, ator), "Parâmetros")

    def titulos(self) -> list[str]:
        return [self.tabText(i) for i in range(self.count())]
