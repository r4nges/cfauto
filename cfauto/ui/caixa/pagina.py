"""Módulo PDV: "Caixa fechado" (com Abrir caixa) ou a tela de venda, conforme a sessão."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget
from sqlalchemy.orm import Session, sessionmaker

from cfauto.caixa.sessao import sessao_aberta
from cfauto.core.db import transacao
from cfauto.core.permissoes import Ator
from cfauto.ui.caixa.abrir import DialogoAbrirCaixa
from cfauto.ui.caixa.pdv import TelaPdv


class PaginaCaixa(QStackedWidget):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator

        self.fechado = QWidget()
        aviso = QLabel("<h2>Caixa fechado</h2><p>Abra o caixa para vender e receber crediário.</p>")
        aviso.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.botao_abrir = QPushButton("Abrir caixa")
        self.botao_abrir.clicked.connect(self._abrir_caixa)
        layout = QVBoxLayout(self.fechado)
        layout.addStretch()
        layout.addWidget(aviso)
        layout.addWidget(self.botao_abrir, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

        self.pdv = TelaPdv(fabrica, ator)
        self.pdv.sessao_encerrada.connect(self.recarregar)
        self.addWidget(self.fechado)
        self.addWidget(self.pdv)
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            painel = sessao_aberta(s, self._ator)
        if painel is None:
            self.setCurrentWidget(self.fechado)
            return
        self.pdv.recarregar()
        self.setCurrentWidget(self.pdv)

    def _abrir_caixa(self) -> None:
        if DialogoAbrirCaixa(self._fabrica, self._ator, self).exec():
            self.recarregar()
