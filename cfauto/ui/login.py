from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

        self.campo_login = QLineEdit()
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        if login_fixo is not None:
            self.campo_login.setText(login_fixo)
            self.campo_login.setEnabled(False)
        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setStyleSheet("color: #c0392b;")

        form = QFormLayout()
        form.addRow("Login", self.campo_login)
        form.addRow("Senha", self.campo_senha)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Entrar")
        botoes.accepted.connect(self.entrar)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.rotulo_erro)
        layout.addWidget(botoes)
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
