from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cfauto.core.errors import ErroDominio, ValorInvalido
from cfauto.core.money import para_decimal


class PaginaEmConstrucao(QWidget):
    def __init__(self, titulo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        rotulo = QLabel(f"<h2>{titulo}</h2><p>Módulo em construção.</p>")
        rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(rotulo)


def mostrar_erro(parent: QWidget | None, erro: Exception) -> None:
    if isinstance(erro, ErroDominio):
        QMessageBox.warning(parent, "CFAUTO", str(erro))
    else:
        QMessageBox.critical(parent, "CFAUTO", f"Erro inesperado: {erro}")


def criar_tabela(colunas: list[str]) -> QTableWidget:
    """Tabela só leitura, com seleção de uma linha inteira."""
    tabela = QTableWidget(0, len(colunas))
    tabela.setHorizontalHeaderLabels(colunas)
    tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tabela.horizontalHeader().setStretchLastSection(True)
    tabela.verticalHeader().setVisible(False)
    return tabela


def preencher_tabela(tabela: QTableWidget, linhas: list[list[str]]) -> None:
    tabela.clearSelection()
    tabela.setRowCount(len(linhas))
    for i, valores in enumerate(linhas):
        for j, valor in enumerate(valores):
            tabela.setItem(i, j, QTableWidgetItem(valor))
    tabela.resizeColumnsToContents()


def ler_decimal(texto: str, rotulo: str) -> Decimal:
    """Texto digitado (formato brasileiro) → Decimal; o erro já traz o nome do campo."""
    try:
        return para_decimal(texto)
    except ValorInvalido as erro:
        raise ValorInvalido(f"{rotulo}: {erro}") from erro


def ler_decimal_opcional(texto: str, rotulo: str) -> Decimal | None:
    return None if not texto.strip() else ler_decimal(texto, rotulo)
