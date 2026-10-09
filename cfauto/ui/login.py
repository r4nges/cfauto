from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.auth.service import autenticar
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.permissoes import Ator
from cfauto.ui.tema import PainelMarca

TAMANHO_MINIMO = (580, 270)


class DialogoLogin(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        *,
        login_fixo: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self.ator: Ator | None = None
        self.setWindowTitle("CFAUTO — Entrar" if login_fixo is None else "CFAUTO — Tela bloqueada")
        self.setMinimumSize(*TAMANHO_MINIMO)

        self.rotulo_titulo = QLabel("Entrar" if login_fixo is None else "Tela bloqueada")
        self.rotulo_titulo.setProperty("papel", "titulo")
        self.campo_login = QLineEdit()
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        if login_fixo is not None:
            self.campo_login.setText(login_fixo)
            self.campo_login.setEnabled(False)
        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setProperty("papel", "erro")

        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.addRow("Login", self.campo_login)
        form.addRow("Senha", self.campo_senha)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Entrar")
        botoes.accepted.connect(self.entrar)
        botoes.rejected.connect(self.reject)

        coluna = QVBoxLayout()
        coluna.setContentsMargins(26, 22, 26, 20)
        coluna.addWidget(self.rotulo_titulo)
        coluna.addSpacing(8)
        coluna.addLayout(form)
        coluna.addWidget(self.rotulo_erro)
        coluna.addStretch(1)
        coluna.addWidget(botoes)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(PainelMarca())
        layout.addLayout(coluna, 1)
        (self.campo_senha if login_fixo else self.campo_login).setFocus()

    def entrar(self) -> None:
        try:
            with transacao(self._fabrica) as s:
                ator = autenticar(s, self.campo_login.text(), self.campo_senha.text())
        except ErroDominio as erro:
            self.rotulo_erro.setText(str(erro))
            self.campo_senha.clear()
            return
        self.ator = ator
        self.accept()
