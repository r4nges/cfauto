"""Autorização do administrador na hora (login + senha), sem trocar quem está logado."""

from collections.abc import Callable
from html import escape

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.auth.service import autorizar_admin
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.permissoes import Ator
from cfauto.ui.comum import mostrar_erro

Perguntar = Callable[[str], bool]
Autorizar = Callable[[str], Ator | None]


class DialogoAutorizacao(QDialog):
    def __init__(
        self, fabrica: sessionmaker[Session], texto: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self.autorizador: Ator | None = None
        self.setWindowTitle("Autorização do administrador")
        explicacao = QLabel(escape(texto).replace("\n", "<br>"))
        explicacao.setWordWrap(True)
        self.login = QLineEdit()
        self.senha = QLineEdit()
        self.senha.setEchoMode(QLineEdit.EchoMode.Password)
        form = QFormLayout()
        form.addRow("Login do administrador", self.login)
        form.addRow("Senha", self.senha)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.confirmar)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(explicacao)
        layout.addLayout(form)
        layout.addWidget(botoes)

    def confirmar(self) -> None:
        # Transação própria: autenticar() grava a tentativa falha (bloqueio após 5 erros).
        try:
            with transacao(self._fabrica) as s:
                self.autorizador = autorizar_admin(s, self.login.text(), self.senha.text())
        except ErroDominio as erro:
            self.autorizador = None
            self.senha.clear()
            mostrar_erro(self, erro)
            return
        self.accept()


def pedir_autorizacao(
    fabrica: sessionmaker[Session], parent: QWidget | None, texto: str
) -> Ator | None:
    dialogo = DialogoAutorizacao(fabrica, texto, parent)
    try:
        return dialogo.autorizador if dialogo.exec() else None
    finally:
        # O diálogo é filho de `parent`: sem isto ele (e a senha digitada) viveria até o fim do app.
        dialogo.senha.clear()
        dialogo.deleteLater()


def perguntar_padrao(parent: QWidget, texto: str) -> bool:
    """Confirmação Sim/Não padrão das telas do caixa (injetável nos testes por `Perguntar`)."""
    resposta = QMessageBox.question(
        parent,
        "CFAUTO",
        texto,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return resposta == QMessageBox.StandardButton.Yes
