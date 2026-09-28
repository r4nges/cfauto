"""Extrato do cliente: razão por período, com impressão (PDF pela impressora do Windows)."""

from datetime import date, timedelta
from typing import cast

from PySide6.QtCore import QDate
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintPreviewDialog
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.clientes.extrato_html import descrever_lancamento, gerar_html_extrato
from cfauto.clientes.models import TipoLancamento
from cfauto.clientes.razao import extrato
from cfauto.clientes.schemas import Extrato
from cfauto.clientes.validacao import formatar_saldo
from cfauto.core import clock, config
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.money import formatar_brl
from cfauto.core.permissoes import Ator
from cfauto.ui.comum import criar_tabela, mostrar_erro, preencher_tabela

DIAS_PADRAO = 90
_COLUNAS = ["Data/hora", "Descrição", "Débito", "Crédito", "Saldo", "Usuário"]


def _campo_data(valor: date) -> QDateEdit:
    campo = QDateEdit(QDate(valor.year, valor.month, valor.day))
    campo.setCalendarPopup(True)
    campo.setDisplayFormat("dd/MM/yyyy")
    return campo


class DialogoExtrato(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        cliente_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._cliente_id = cliente_id
        self._extrato: Extrato | None = None
        self._loja = ""
        self.setWindowTitle("Extrato")
        self.resize(760, 480)
        hoje = clock.hoje()
        self.inicio = _campo_data(hoje - timedelta(days=DIAS_PADRAO))
        self.fim = _campo_data(hoje)
        atualizar = QPushButton("Atualizar")
        atualizar.clicked.connect(self.recarregar)
        imprimir = QPushButton("Imprimir extrato")
        imprimir.clicked.connect(self.imprimir)
        self.tabela = criar_tabela(_COLUNAS)
        self.saldo_anterior = QLabel()
        self.saldo_final = QLabel()

        periodo = QFormLayout()
        periodo.addRow("De", self.inicio)
        periodo.addRow("Até", self.fim)
        topo = QHBoxLayout()
        topo.addLayout(periodo)
        topo.addWidget(atualizar)
        topo.addStretch()
        topo.addWidget(imprimir)
        layout = QVBoxLayout(self)
        layout.addLayout(topo)
        layout.addWidget(self.saldo_anterior)
        layout.addWidget(self.tabela)
        layout.addWidget(self.saldo_final)
        self.recarregar()

    def recarregar(self) -> None:
        inicio = cast(date, self.inicio.date().toPython())
        fim = cast(date, self.fim.date().toPython())
        try:
            with transacao(self._fabrica) as s:
                self._extrato = extrato(s, self._ator, self._cliente_id, inicio, fim)
                self._loja = str(config.obter(s, "empresa.nome", "") or "")
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        dados = self._extrato
        self.setWindowTitle(f"Extrato — {dados.cliente.codigo} {dados.cliente.nome}")
        preencher_tabela(
            self.tabela,
            [
                [
                    f"{linha.data_hora:%d/%m/%Y %H:%M}",
                    descrever_lancamento(linha),
                    formatar_brl(linha.valor) if linha.tipo == TipoLancamento.DEBITO else "",
                    formatar_brl(linha.valor) if linha.tipo == TipoLancamento.CREDITO else "",
                    formatar_saldo(linha.saldo_apos),
                    linha.usuario,
                ]
                for linha in dados.linhas
            ],
        )
        self.saldo_anterior.setText(f"Saldo anterior: {formatar_saldo(dados.saldo_anterior)}")
        self.saldo_final.setText(f"Saldo final: {formatar_saldo(dados.saldo_final)}")

    def html(self) -> str:
        if self._extrato is None:
            return ""
        return gerar_html_extrato(self._extrato, self._loja, clock.agora())

    def imprimir(self) -> None:
        if self._extrato is None:
            return
        documento = QTextDocument(self)
        documento.setHtml(self.html())
        self._abrir_previa(documento)

    def _abrir_previa(self, documento: QTextDocument) -> None:
        previa = QPrintPreviewDialog(self)
        previa.paintRequested.connect(documento.print_)
        previa.exec()
