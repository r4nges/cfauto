"""Lançamento manual no razão do cliente: aumentar ou abater a dívida."""

from html import escape

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.clientes.models import (
    MOTIVOS_MANUAIS,
    TITULOS_MOTIVO_LANCAMENTO,
    MotivoLancamento,
    TipoLancamento,
)
from cfauto.clientes.razao import TAMANHO_OBSERVACAO, lancar_manual, saldo_apos
from cfauto.clientes.schemas import ResumoCliente
from cfauto.clientes.validacao import formatar_saldo
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio, ValorInvalido
from cfauto.core.money import arredondar
from cfauto.core.permissoes import Ator
from cfauto.ui.comum import ler_decimal, mostrar_erro


class DialogoLancamento(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        cliente: ResumoCliente,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._cliente = cliente
        self.setWindowTitle(f"Lançamento — {cliente.codigo}")
        cabecalho = QLabel(
            f"<b>{escape(cliente.codigo)} — {escape(cliente.nome)}</b><br>"
            f"Saldo atual: {escape(formatar_saldo(cliente.saldo_devedor))}"
        )
        self.aumentar = QRadioButton("Aumentar dívida")
        self.abater = QRadioButton("Abater dívida")
        self.aumentar.setChecked(True)
        self.valor = QLineEdit()
        self.motivo = QComboBox()
        for motivo in MOTIVOS_MANUAIS:
            self.motivo.addItem(TITULOS_MOTIVO_LANCAMENTO[motivo], motivo)
        self.observacao = QLineEdit()
        self.observacao.setMaxLength(TAMANHO_OBSERVACAO)
        self.previa = QLabel()
        self.aumentar.toggled.connect(self._atualizar_previa)
        self.valor.textChanged.connect(self._atualizar_previa)

        tipos = QHBoxLayout()
        tipos.addWidget(self.aumentar)
        tipos.addWidget(self.abater)
        form = QFormLayout()
        form.addRow("", tipos)
        form.addRow("Valor", self.valor)
        form.addRow("Motivo", self.motivo)
        form.addRow("Observação", self.observacao)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.salvar)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(cabecalho)
        layout.addLayout(form)
        layout.addWidget(self.previa)
        layout.addWidget(botoes)
        self._atualizar_previa()

    def tipo(self) -> TipoLancamento:
        return TipoLancamento.DEBITO if self.aumentar.isChecked() else TipoLancamento.CREDITO

    def _atualizar_previa(self) -> None:
        try:
            valor = arredondar(ler_decimal(self.valor.text(), "Valor"))
        except ValorInvalido:
            # Valor incompleto enquanto o usuário digita: sem prévia; o erro vem ao salvar.
            self.previa.setText("Saldo após: —")
            return
        if valor <= 0:
            # Arredonda a zero ou menos: `lancar` vai rejeitar; não mostrar prévia enganosa.
            self.previa.setText("Saldo após: —")
            return
        novo = saldo_apos(self._cliente.saldo_devedor, self.tipo(), valor)
        self.previa.setText(f"Saldo após: {formatar_saldo(novo)}")

    def salvar(self) -> None:
        try:
            valor = ler_decimal(self.valor.text(), "Valor")
            with transacao(self._fabrica) as s:
                lancar_manual(
                    s,
                    self._ator,
                    self._cliente.id,
                    self.tipo(),
                    valor,
                    MotivoLancamento(self.motivo.currentData()),
                    self.observacao.text(),
                )
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()
