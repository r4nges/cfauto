from PySide6.QtWidgets import QTabWidget, QWidget
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.permissoes import Ator
from cfauto.ui.estoque.entradas import TelaEntradas
from cfauto.ui.estoque.produtos import TelaProdutos
from cfauto.ui.estoque.servicos import TelaServicos


class PaginaEstoque(QTabWidget):
    """Módulo Estoque: produtos, serviços e entradas de NF-e."""

    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.produtos = TelaProdutos(fabrica, ator)
        self.servicos = TelaServicos(fabrica, ator)
        self.entradas = TelaEntradas(fabrica, ator)
        self.addTab(self.produtos, "Produtos")
        self.addTab(self.servicos, "Serviços")
        self.addTab(self.entradas, "Entradas de NF-e")
        self.currentChanged.connect(self._ao_trocar_aba)

    def titulos(self) -> list[str]:
        return [self.tabText(i) for i in range(self.count())]

    def _ao_trocar_aba(self, _indice: int) -> None:
        # Uma entrada ou estorno muda estoque e custo: a aba mostrada é sempre recarregada.
        atual = self.currentWidget()
        if isinstance(atual, TelaProdutos | TelaServicos | TelaEntradas):
            atual.recarregar()
