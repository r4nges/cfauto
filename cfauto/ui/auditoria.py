import json
from datetime import date, datetime, time
from typing import cast

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.auth.auditoria import consultar
from cfauto.core import clock
from cfauto.core.db import transacao
from cfauto.core.permissoes import Ator

_COLUNAS = ["Data/hora", "Usuário", "Ação", "Entidade", "ID", "Antes", "Depois"]


def _json(valor: object) -> str:
    return "" if valor is None else json.dumps(valor, ensure_ascii=False)


class TelaAuditoria(QWidget):
    def __init__(self, fabrica: sessionmaker[Session], ator: Ator) -> None:
        super().__init__()
        self._fabrica = fabrica
        self._ator = ator

        self.filtro_entidade = QLineEdit()
        self.filtro_entidade.setPlaceholderText("entidade (ex.: produto)")
        hoje = clock.hoje()
        self.desde = QDateEdit(QDate(hoje.year, hoje.month, hoje.day).addDays(-30))
        self.ate = QDateEdit(QDate(hoje.year, hoje.month, hoje.day))
        for campo in (self.desde, self.ate):
            campo.setCalendarPopup(True)
            campo.setDisplayFormat("dd/MM/yyyy")
        botao = QPushButton("Filtrar")
        botao.clicked.connect(self.filtrar)

        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Entidade"))
        filtros.addWidget(self.filtro_entidade)
        filtros.addWidget(QLabel("De"))
        filtros.addWidget(self.desde)
        filtros.addWidget(QLabel("Até"))
        filtros.addWidget(self.ate)
        filtros.addWidget(botao)

        self.tabela = QTableWidget(0, len(_COLUNAS))
        self.tabela.setHorizontalHeaderLabels(_COLUNAS)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.horizontalHeader().setStretchLastSection(True)

        layout = QVBoxLayout(self)
        layout.addLayout(filtros)
        layout.addWidget(self.tabela)
        self.filtrar()

    def filtrar(self) -> None:
        desde = datetime.combine(cast(date, self.desde.date().toPython()), time.min)
        ate = datetime.combine(cast(date, self.ate.date().toPython()), time.max)
        with transacao(self._fabrica) as s:
            registros = consultar(
                s,
                self._ator,
                entidade=self.filtro_entidade.text().strip() or None,
                desde=desde,
                ate=ate,
            )
        self.tabela.setRowCount(len(registros))
        for linha, r in enumerate(registros):
            valores = [
                f"{r.timestamp:%d/%m/%Y %H:%M:%S}",
                r.usuario_nome or "(sistema)",
                r.acao,
                r.entidade,
                r.entidade_id or "",
                _json(r.antes),
                _json(r.depois),
            ]
            for coluna, valor in enumerate(valores):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(valor))
