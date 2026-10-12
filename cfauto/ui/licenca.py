from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.db import transacao
from cfauto.core.errors import LicencaInvalida
from cfauto.licenca import service
from cfauto.licenca.maquina import id_maquina
from cfauto.ui.tema import PainelMarca

TAMANHO_MINIMO = (640, 360)


class DialogoLicenca(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        estado: service.EstadoLicenca,
        *,
        publica: Ed25519PublicKey | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._publica = publica
        self.estado = estado
        self.setWindowTitle("CFAUTO — Licença")
        self.setMinimumSize(*TAMANHO_MINIMO)

        self.rotulo_titulo = QLabel("Ativar licença")
        self.rotulo_titulo.setProperty("papel", "titulo")
        motivo = QLabel(estado.mensagem)
        motivo.setWordWrap(True)
        campo_maquina = QLineEdit(id_maquina())
        campo_maquina.setReadOnly(True)
        self.campo_chave = QPlainTextEdit()
        self.campo_chave.setPlaceholderText("Cole aqui a chave de licença")
        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setProperty("papel", "erro")

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addRow("ID desta máquina", campo_maquina)
        form.addRow("Chave", self.campo_chave)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Instalar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        botoes.accepted.connect(self.instalar)
        botoes.rejected.connect(self.reject)

        coluna = QVBoxLayout()
        coluna.setContentsMargins(26, 22, 26, 20)
        coluna.addWidget(self.rotulo_titulo)
        coluna.addSpacing(4)
        coluna.addWidget(motivo)
        coluna.addSpacing(8)
        coluna.addLayout(form)
        coluna.addWidget(self.rotulo_erro)
        coluna.addWidget(botoes)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(PainelMarca())
        layout.addLayout(coluna, 1)

    def instalar(self) -> None:
        try:
            with transacao(self._fabrica) as s:
                estado = service.instalar(s, self.campo_chave.toPlainText(), publica=self._publica)
        except LicencaInvalida as erro:
            self.rotulo_erro.setText(str(erro))
            return
        self.estado = estado
        self.accept()
