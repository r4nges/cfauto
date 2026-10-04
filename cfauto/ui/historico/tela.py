"""Histórico: vendas e sessões de caixa já fechadas (só leitura)."""

from collections.abc import Callable
from datetime import date
from typing import cast

from PySide6.QtCore import QDate, QModelIndex, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.caixa.models import TITULOS_FORMA, TITULOS_TIPO_VENDA, FormaPagamento, TipoVenda
from cfauto.core import clock
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio, ValorInvalido
from cfauto.core.money import formatar_brl, formatar_qtd
from cfauto.core.permissoes import Ator
from cfauto.core.texto import normalizar_texto
from cfauto.historico.consultas import (
    DetalheVenda,
    FiltroHistorico,
    LinhaHistorico,
    LinhaSessao,
    detalhe_venda,
    listar_sessoes,
    listar_vendas,
)
from cfauto.ui.caixa.formatos import descrever_resumo
from cfauto.ui.comum import criar_tabela, mostrar_erro, preencher_tabela

_COLUNAS_VENDAS = [
    "Protocolo",
    "Data/hora",
    "Descrição",
    "Cliente",
    "Tipo",
    "Forma",
    "Bruto",
    "Taxa",
    "Líquido",
    "Dias p/ liquidar",
    "Situação",
]
_COLUNAS_SESSOES = [
    "Protocolo",
    "Abertura",
    "Fechamento",
    "Aberto por",
    "Fechado por",
    "Fundo",
    "Total vendido",
    "Gaveta",
    "Mantido",
    "Sangria",
]


def _campo_data(valor: date) -> QDateEdit:
    campo = QDateEdit(QDate(valor.year, valor.month, valor.day))
    campo.setCalendarPopup(True)
    campo.setDisplayFormat("dd/MM/yyyy")
    return campo


def _data(campo: QDateEdit) -> date:
    return cast(date, campo.date().toPython())


def _celulas_venda(v: LinhaHistorico) -> list[str]:
    return [
        v.protocolo,
        f"{v.data_hora:%d/%m/%Y %H:%M}",
        v.descricao,
        v.cliente or "",
        TITULOS_TIPO_VENDA[v.tipo],
        TITULOS_FORMA[v.forma],
        formatar_brl(v.bruto),
        formatar_brl(v.taxa),
        formatar_brl(v.liquido),
        "—" if v.dias_liquidacao is None else str(v.dias_liquidacao),
        "Cancelada" if v.cancelada else "Ativa",
    ]


def _celulas_sessao(x: LinhaSessao) -> list[str]:
    return [
        x.protocolo,
        f"{x.aberta_em:%d/%m/%Y %H:%M}",
        f"{x.fechada_em:%d/%m/%Y %H:%M}",
        x.aberta_por,
        x.fechada_por,
        formatar_brl(x.resumo.fundo_troco),
        formatar_brl(x.resumo.total_vendido),
        formatar_brl(x.resumo.gaveta),
        formatar_brl(x.valor_mantido),
        formatar_brl(x.sangria),
    ]


def _texto_detalhe(d: DetalheVenda) -> str:
    v = d.linha
    linhas = [f"{v.protocolo} · {v.data_hora:%d/%m/%Y %H:%M} · {TITULOS_FORMA[v.forma]}"]
    if v.tipo == TipoVenda.RECEBIMENTO:
        linhas.append(v.descricao)
    linhas += [
        f"{formatar_qtd(item.qtd)} × {item.descricao} ({item.categoria})"
        f" — {formatar_brl(item.subtotal)}"
        for item in d.itens
    ]
    linhas.append(f"Desconto: {formatar_brl(d.desconto)}")
    linhas.append(
        f"Bruto: {formatar_brl(v.bruto)} · Taxa: {formatar_brl(v.taxa)}"
        f" · Líquido: {formatar_brl(v.liquido)}"
    )
    if v.cliente:
        linhas.append(f"Cliente: {v.cliente}")
    linhas.append(f"Usuário: {d.usuario}")
    if d.autorizado_por:
        linhas.append(f"Venda sem estoque autorizada por: {d.autorizado_por}")
    if v.cancelada:
        autorizacao = (
            f" (autorizado por {d.cancelamento_autorizado_por})"
            if d.cancelamento_autorizado_por
            else ""
        )
        linhas.append(
            f"Cancelada por {d.cancelada_por}{autorizacao}: {d.motivo_cancelamento or ''}"
        )
    return "\n".join(linhas)


class TelaHistorico(QTabWidget):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._vendas: list[LinhaHistorico] = []
        self._sessoes: list[LinhaSessao] = []
        self._exibir: Callable[[str, str], None] = self._exibir_padrao

        hoje = clock.hoje()
        self.inicio = _campo_data(hoje.replace(day=1))
        self.fim = _campo_data(hoje)
        atualizar = QPushButton("Atualizar")
        atualizar.clicked.connect(self.recarregar)
        periodo = QWidget()
        linha_periodo = QHBoxLayout(periodo)
        linha_periodo.setContentsMargins(0, 0, 0, 0)
        for rotulo, campo in (("De", self.inicio), ("Até", self.fim)):
            linha_periodo.addWidget(QLabel(rotulo))
            linha_periodo.addWidget(campo)
        linha_periodo.addWidget(atualizar)
        # O período vale para as duas abas.
        self.setCornerWidget(periodo, Qt.Corner.TopRightCorner)

        self.forma = QComboBox()
        self.forma.addItem("Todas", None)
        for forma in FormaPagamento:
            self.forma.addItem(TITULOS_FORMA[forma], forma)
        self.tipo = QComboBox()
        self.tipo.addItem("Todos", None)
        for tipo in TipoVenda:
            self.tipo.addItem(TITULOS_TIPO_VENDA[tipo], tipo)
        self.cliente = QLineEdit()
        self.cliente.setPlaceholderText("Cliente (nome)")
        self.incluir_canceladas = QCheckBox("Incluir canceladas")
        self.vendas = criar_tabela(_COLUNAS_VENDAS)
        self.vendas.doubleClicked.connect(self._detalhar_venda)
        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Forma"))
        filtros.addWidget(self.forma)
        filtros.addWidget(QLabel("Tipo"))
        filtros.addWidget(self.tipo)
        filtros.addWidget(self.cliente)
        filtros.addWidget(self.incluir_canceladas)
        filtros.addStretch()
        aba_vendas = QWidget()
        layout_vendas = QVBoxLayout(aba_vendas)
        layout_vendas.addLayout(filtros)
        layout_vendas.addWidget(self.vendas)

        self.sessoes = criar_tabela(_COLUNAS_SESSOES)
        self.sessoes.doubleClicked.connect(self._detalhar_sessao)
        aba_sessoes = QWidget()
        layout_sessoes = QVBoxLayout(aba_sessoes)
        # A sessão entra pelo dia do fechamento; as vendas, pelo dia de cada uma (consultas.py).
        layout_sessoes.addWidget(QLabel("Sessões com fechamento no período. Duplo clique: resumo."))
        layout_sessoes.addWidget(self.sessoes)

        self.addTab(aba_vendas, "Vendas")
        self.addTab(aba_sessoes, "Sessões")
        self.recarregar()
        self.forma.currentIndexChanged.connect(self.recarregar)
        self.tipo.currentIndexChanged.connect(self.recarregar)
        self.incluir_canceladas.toggled.connect(self.recarregar)
        self.cliente.returnPressed.connect(self.recarregar)

    def recarregar(self) -> None:
        inicio, fim = _data(self.inicio), _data(self.fim)
        if fim < inicio:
            mostrar_erro(self, ValorInvalido("A data final é anterior à inicial."))
            return
        forma = self.forma.currentData()
        tipo = self.tipo.currentData()
        filtro = FiltroHistorico(
            inicio=inicio,
            fim=fim,
            forma=None if forma is None else FormaPagamento(forma),
            tipo=None if tipo is None else TipoVenda(tipo),
            incluir_canceladas=self.incluir_canceladas.isChecked(),
        )
        try:
            with transacao(self._fabrica) as s:
                vendas = listar_vendas(s, self._ator, filtro)
                sessoes = listar_sessoes(s, self._ator, inicio, fim)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        termo = normalizar_texto(self.cliente.text())
        if termo:
            vendas = [v for v in vendas if v.cliente and termo in normalizar_texto(v.cliente)]
        self._vendas = vendas
        self._sessoes = sessoes
        preencher_tabela(self.vendas, [_celulas_venda(v) for v in vendas])
        preencher_tabela(self.sessoes, [_celulas_sessao(x) for x in sessoes])

    def _detalhar_venda(self, indice: QModelIndex) -> None:
        linha = indice.row()
        if not 0 <= linha < len(self._vendas):
            return
        venda_id = self._vendas[linha].venda_id
        try:
            with transacao(self._fabrica) as s:
                detalhe = detalhe_venda(s, self._ator, venda_id)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self._exibir(f"Venda nº {venda_id}", _texto_detalhe(detalhe))

    def _detalhar_sessao(self, indice: QModelIndex) -> None:
        linha = indice.row()
        if not 0 <= linha < len(self._sessoes):
            return
        sessao = self._sessoes[linha]
        texto = (
            f"{descrever_resumo(sessao.resumo)}\n"
            f"Valor mantido: {formatar_brl(sessao.valor_mantido)}\n"
            f"Sangria: {formatar_brl(sessao.sangria)}"
        )
        self._exibir(f"Sessão {sessao.protocolo}", texto)

    def _exibir_padrao(self, titulo: str, texto: str) -> None:
        QMessageBox.information(self, titulo, texto)
