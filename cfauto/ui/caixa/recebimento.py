"""Receber crediário: abate a dívida do cliente e entra no caixa pela forma usada."""

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.caixa.calculo import calcular_pagamento, troco
from cfauto.caixa.models import FORMAS_COM_TAXA, TITULOS_FORMA, FormaPagamento
from cfauto.caixa.recebimento import registrar_recebimento
from cfauto.caixa.schemas import Pagamento, TaxaForma
from cfauto.caixa.taxas import listar_taxas
from cfauto.clientes.cadastro import obter_cliente
from cfauto.clientes.schemas import FichaCliente
from cfauto.clientes.validacao import formatar_saldo
from cfauto.core import clock
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio, ValorInvalido
from cfauto.core.money import arredondar, formatar_brl
from cfauto.core.permissoes import Ator
from cfauto.ui.caixa.autorizacao import Perguntar, perguntar_padrao
from cfauto.ui.caixa.formatos import BuscaCliente
from cfauto.ui.comum import ler_decimal, ler_decimal_opcional, mostrar_erro


class DialogoRecebimento(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        parent: QWidget | None = None,
        *,
        perguntar: Perguntar | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._perguntar: Perguntar = perguntar or (lambda texto: perguntar_padrao(self, texto))
        self._cliente: FichaCliente | None = None
        self.venda_id: int | None = None
        with transacao(fabrica) as s:
            self._taxas: dict[FormaPagamento, TaxaForma] = {
                taxa.forma: taxa for taxa in listar_taxas(s, ator)
            }
        self.setWindowTitle("Receber crediário")

        self._info = QLabel("Selecione o cliente.")
        self._info.setTextFormat(Qt.TextFormat.PlainText)
        self._busca = BuscaCliente(
            fabrica,
            ator,
            "Nome, código, CPF ou celular — Enter",
            ao_escolher=self.definir_cliente,
            ao_avisar=self._info.setText,
        )
        self.valor = QLineEdit()
        self.forma = QComboBox()
        for forma in FORMAS_COM_TAXA:
            self.forma.addItem(TITULOS_FORMA[forma], forma)
        self.recebido = QLineEdit()
        self._previa = QLabel()
        self._previa.setTextFormat(Qt.TextFormat.PlainText)
        self.valor.textChanged.connect(self._atualizar_previa)
        self.recebido.textChanged.connect(self._atualizar_previa)
        self.forma.currentIndexChanged.connect(self._ao_trocar_forma)

        form = QFormLayout()
        form.addRow("Cliente", self._busca.campo)
        form.addRow("", self._busca.opcoes)
        form.addRow("", self._info)
        form.addRow("Valor a abater", self.valor)
        form.addRow("Forma", self.forma)
        form.addRow("Recebido (dinheiro)", self.recebido)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.salvar)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._previa)
        layout.addWidget(botoes)
        self._ao_trocar_forma()
        self._busca.campo.setFocus()

    def definir_cliente(self, cliente_id: int) -> None:
        try:
            with transacao(self._fabrica) as s:
                self._cliente = obter_cliente(s, self._ator, cliente_id)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        c = self._cliente
        self._info.setText(
            f"{c.codigo} — {c.dados.nome} · Saldo: {formatar_saldo(c.saldo_devedor)}"
        )

    def _forma(self) -> FormaPagamento:
        return FormaPagamento(self.forma.currentData())

    def _ao_trocar_forma(self) -> None:
        dinheiro = self._forma() == FormaPagamento.DINHEIRO
        if not dinheiro:
            self.recebido.clear()
        self.recebido.setEnabled(dinheiro)
        self._atualizar_previa()

    def _pagamento(self, valor: Decimal) -> Pagamento:
        forma = self._forma()
        return calcular_pagamento(valor, forma, self._taxas.get(forma), clock.hoje())

    def _atualizar_previa(self) -> None:
        try:
            pagamento = self._pagamento(arredondar(ler_decimal(self.valor.text(), "Valor")))
        except ValorInvalido:
            self._previa.setText("Total a cobrar: —")
            return
        texto = f"Total a cobrar: {formatar_brl(pagamento.cobrado)}"
        recebido = self.recebido.text().strip()
        if self._forma() == FormaPagamento.DINHEIRO and recebido:
            try:
                valor_troco = troco(pagamento.cobrado, ler_decimal(recebido, "Recebido"))
            except ValorInvalido:
                texto += " · Troco: —"
            else:
                texto += f" · Troco: {formatar_brl(valor_troco)}"
        self._previa.setText(texto)

    def salvar(self) -> None:
        cliente = self._cliente
        if cliente is None:
            mostrar_erro(self, ValorInvalido("Selecione o cliente."))
            return
        try:
            valor = arredondar(ler_decimal(self.valor.text(), "Valor"))
            pagamento = self._pagamento(valor)
            if self._forma() == FormaPagamento.DINHEIRO:
                recebido = ler_decimal_opcional(self.recebido.text(), "Recebido")
                if recebido is not None:
                    troco(pagamento.cobrado, recebido)
        except ValorInvalido as erro:
            mostrar_erro(self, erro)
            return
        divida = max(cliente.saldo_devedor, Decimal(0))
        if valor > divida:
            texto = (
                f"O valor passa da dívida ({formatar_saldo(cliente.saldo_devedor)}). "
                f"O excedente de {formatar_brl(valor - divida)} vira crédito a favor do "
                "cliente. Continuar?"
            )
            if not self._perguntar(texto):
                return
        try:
            with transacao(self._fabrica) as s:
                self.venda_id = registrar_recebimento(
                    s, self._ator, cliente.id, valor, self._forma()
                )
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()
