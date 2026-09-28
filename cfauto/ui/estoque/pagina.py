from PySide6.QtWidgets import QTabWidget, QWidget
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.permissoes import Ator
from cfauto.ui.estoque.produtos import TelaProdutos
from cfauto.ui.estoque.servicos import TelaServicos


class PaginaEstoque(QTabWidget):
    """Módulo Estoque: produtos, serviços e entradas de NF-e."""

    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.produtos = TelaProdutos(fabrica, ator)
        self.addTab(self.produtos, "Produtos")
        self.servicos = TelaServicos(fabrica, ator)
        self.addTab(self.servicos, "Serviços")

    def titulos(self) -> list[str]:
        return [self.tabText(i) for i in range(self.count())]
