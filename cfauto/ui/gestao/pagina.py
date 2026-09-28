from PySide6.QtWidgets import QTabWidget, QWidget
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.permissoes import Ator
from cfauto.ui.gestao.bens import TelaBens


class PaginaGestao(QTabWidget):
    """Aba CFAUTO de Configurações. Markup, DRE e demais painéis chegam nos sub-projetos 6 e 7."""

    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.bens = TelaBens(fabrica, ator)
        self.addTab(self.bens, "Bens Físicos")

    def titulos(self) -> list[str]:
        return [self.tabText(i) for i in range(self.count())]
