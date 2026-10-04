"""Abertura do caixa: fundo de troco, sugerido pelo valor mantido no último fechamento."""

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

from cfauto.caixa.sessao import abrir_sessao, sugestao_fundo
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.money import formatar_numero
from cfauto.core.permissoes import Ator
from cfauto.ui.comum import ler_decimal, mostrar_erro


class DialogoAbrirCaixa(QDialog):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        with transacao(fabrica) as s:
            sugestao = sugestao_fundo(s, ator)
        self.setWindowTitle("Abrir caixa")
        self.fundo = QLineEdit(formatar_numero(sugestao))
        form = QFormLayout()
        form.addRow("Fundo de troco (R$)", self.fundo)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = botoes.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText("Abrir caixa")
        botoes.accepted.connect(self.abrir)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Informe o dinheiro que fica na gaveta para troco."))
        layout.addLayout(form)
        layout.addWidget(botoes)

    def abrir(self) -> None:
        try:
            fundo = ler_decimal(self.fundo.text(), "Fundo de troco")
            with transacao(self._fabrica) as s:
                abrir_sessao(s, self._ator, fundo)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()
