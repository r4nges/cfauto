from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QVBoxLayout, QWidget

from cfauto.core.errors import ErroDominio


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
