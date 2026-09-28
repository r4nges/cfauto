"""Bens Físicos (Configurações › CFAUTO): Ativo Não Circulante do Balancete."""

from datetime import date
from typing import cast

from PySide6.QtCore import QDate, QModelIndex
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core import clock
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.money import formatar_brl, formatar_numero
from cfauto.core.permissoes import Ator
from cfauto.gestao.bens import (
    atualizar_bem,
    baixar_bem,
    criar_bem,
    listar_bens,
    reativar_bem,
    total_bens_ativos,
)
from cfauto.gestao.models import TITULOS_TIPO_BEM, BemFisico, TipoBem
from cfauto.gestao.schemas import DadosBem
from cfauto.ui.comum import criar_tabela, ler_decimal, mostrar_erro, preencher_tabela

_COLUNAS = ["Código", "Descrição", "Tipo", "Valor", "Data", "Situação"]


class DialogoBem(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        bem: BemFisico | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._bem = bem
        self.setWindowTitle("Novo bem" if bem is None else f"Editar bem {bem.codigo}")
        self.descricao = QLineEdit("" if bem is None else bem.descricao)
        self.tipo = QComboBox()
        for tipo in TipoBem:
            self.tipo.addItem(TITULOS_TIPO_BEM[tipo], tipo)
        if bem is not None:
            self.tipo.setCurrentIndex(list(TipoBem).index(bem.tipo))
        self.valor = QLineEdit("" if bem is None else formatar_numero(bem.valor))
        data = clock.hoje() if bem is None else bem.data_cadastro
        self.data = QDateEdit(QDate(data.year, data.month, data.day))
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        form = QFormLayout()
        form.addRow("Descrição", self.descricao)
        form.addRow("Tipo", self.tipo)
        form.addRow("Valor", self.valor)
        form.addRow("Data", self.data)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.salvar)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botoes)

    def salvar(self) -> None:
        try:
            dados = DadosBem(
                descricao=self.descricao.text(),
                tipo=TipoBem(self.tipo.currentData()),
                valor=ler_decimal(self.valor.text(), "Valor"),
                data_cadastro=cast(date, self.data.date().toPython()),
            )
            with transacao(self._fabrica) as s:
                if self._bem is None:
                    criar_bem(s, self._ator, dados)
                else:
                    atualizar_bem(s, self._ator, self._bem.id, dados)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()


class TelaBens(QWidget):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._bens: list[BemFisico] = []

        self.mostrar_baixados = QCheckBox("Mostrar baixados")
        self.mostrar_baixados.toggled.connect(self.recarregar)
        novo = QPushButton("Novo")
        novo.clicked.connect(self._novo)
        editar = QPushButton("Editar")
        editar.clicked.connect(self._editar)
        self.botao_situacao = QPushButton("Baixar")
        self.botao_situacao.clicked.connect(self.alternar_situacao)
        self.tabela = criar_tabela(_COLUNAS)
        self.tabela.doubleClicked.connect(self._editar_pelo_duplo_clique)
        self.tabela.itemSelectionChanged.connect(self._atualizar_botao_situacao)
        self.total_rotulo = QLabel()

        botoes = QHBoxLayout()
        for botao in (novo, editar, self.botao_situacao):
            botoes.addWidget(botao)
        botoes.addStretch()
        botoes.addWidget(self.mostrar_baixados)
        layout = QVBoxLayout(self)
        layout.addLayout(botoes)
        layout.addWidget(self.tabela)
        layout.addWidget(self.total_rotulo)
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            self._bens = listar_bens(
                s, self._ator, incluir_baixados=self.mostrar_baixados.isChecked()
            )
            total = total_bens_ativos(s, self._ator)
        preencher_tabela(
            self.tabela,
            [
                [
                    bem.codigo,
                    bem.descricao,
                    TITULOS_TIPO_BEM[bem.tipo],
                    formatar_brl(bem.valor),
                    f"{bem.data_cadastro:%d/%m/%Y}",
                    "Ativo" if bem.ativo else "Baixado",
                ]
                for bem in self._bens
            ],
        )
        self.total_rotulo.setText(f"Total dos bens ativos: {formatar_brl(total)}")
        self._atualizar_botao_situacao()

    def codigos_na_tabela(self) -> list[str]:
        return [bem.codigo for bem in self._bens]

    def selecionar(self, linha: int) -> None:
        self.tabela.setCurrentCell(linha, 0)

    def selecionado(self) -> BemFisico | None:
        linha = self.tabela.currentRow()
        return self._bens[linha] if 0 <= linha < len(self._bens) else None

    def _novo(self) -> None:
        if DialogoBem(self._fabrica, self._ator, parent=self).exec():
            self.recarregar()

    def _editar(self) -> None:
        bem = self.selecionado()
        if bem is not None and DialogoBem(self._fabrica, self._ator, bem, self).exec():
            self.recarregar()

    def _editar_pelo_duplo_clique(self, _indice: QModelIndex) -> None:
        self._editar()

    def alternar_situacao(self) -> None:
        bem = self.selecionado()
        if bem is None:
            return
        try:
            with transacao(self._fabrica) as s:
                if bem.ativo:
                    baixar_bem(s, self._ator, bem.id)
                else:
                    reativar_bem(s, self._ator, bem.id)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.recarregar()

    def _atualizar_botao_situacao(self) -> None:
        bem = self.selecionado()
        baixado = bem is not None and not bem.ativo
        self.botao_situacao.setText("Reativar" if baixado else "Baixar")
