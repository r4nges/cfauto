"""Fechamento do caixa: resumo por forma, valor mantido na gaveta e sangria."""

from PySide6.QtCore import Qt
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

from cfauto.caixa.calculo import calcular_sangria
from cfauto.caixa.schemas import FechamentoSessao
from cfauto.caixa.sessao import fechar_sessao, previa_fechamento, sessao_aberta
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio, SessaoFechada, ValorInvalido
from cfauto.core.money import formatar_brl, formatar_numero
from cfauto.core.permissoes import Ator
from cfauto.ui.caixa.autorizacao import Perguntar, perguntar_padrao
from cfauto.ui.caixa.formatos import descrever_resumo
from cfauto.ui.comum import ler_decimal, mostrar_erro


class DialogoFechamento(QDialog):
    """Levanta SessaoFechada no construtor se não houver caixa aberto (quem abre trata)."""

    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        parent: QWidget | None = None,
        *,
        perguntar: Perguntar | None = None,
    ) -> None:
        # A sessão é conferida antes do `super().__init__`: se não houver caixa aberto, nenhum
        # diálogo pela metade fica pendurado na tela que o abriu.
        with transacao(fabrica) as s:
            painel = sessao_aberta(s, ator)
            if painel is None:
                raise SessaoFechada("Caixa fechado: não há caixa aberto para fechar.")
            resumo = previa_fechamento(s, ator)
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._perguntar: Perguntar = perguntar or (lambda texto: perguntar_padrao(self, texto))
        self._resumo = resumo
        self._protocolo = painel.protocolo
        self.fechamento: FechamentoSessao | None = None
        self.setWindowTitle(f"Fechar caixa — {self._protocolo}")
        self.resumo = QLabel(descrever_resumo(resumo))
        self.resumo.setTextFormat(Qt.TextFormat.PlainText)
        self.valor_mantido = QLineEdit(formatar_numero(resumo.fundo_troco))
        self.valor_mantido.textChanged.connect(self._atualizar_sangria)
        self.sangria = QLabel()
        self.sangria.setTextFormat(Qt.TextFormat.PlainText)
        form = QFormLayout()
        form.addRow("Valor mantido na gaveta (R$)", self.valor_mantido)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = botoes.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText("Fechar caixa")
        botoes.accepted.connect(self.fechar)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.resumo)
        layout.addLayout(form)
        layout.addWidget(self.sangria)
        layout.addWidget(botoes)
        self._atualizar_sangria()
        self.valor_mantido.setFocus()
        self.valor_mantido.selectAll()

    def _atualizar_sangria(self) -> None:
        try:
            mantido = ler_decimal(self.valor_mantido.text(), "Valor mantido")
            sangria = calcular_sangria(self._resumo.gaveta, mantido)
        except ValorInvalido as erro:
            self.sangria.setText(f"Sangria: — ({erro})")
            return
        self.sangria.setText(f"Sangria: {formatar_brl(sangria)}")

    def fechar(self) -> None:
        try:
            mantido = ler_decimal(self.valor_mantido.text(), "Valor mantido")
            sangria = calcular_sangria(self._resumo.gaveta, mantido)
        except ValorInvalido as erro:
            mostrar_erro(self, erro)
            return
        texto = (
            f"Fechar o caixa {self._protocolo}? Sangria de {formatar_brl(sangria)}. "
            "Depois de fechado, nenhuma venda desta sessão pode ser cancelada."
        )
        if not self._perguntar(texto):
            return
        try:
            with transacao(self._fabrica) as s:
                self.fechamento = fechar_sessao(s, self._ator, mantido)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()
