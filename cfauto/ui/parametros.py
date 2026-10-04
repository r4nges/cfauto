"""Configurações › Parâmetros: taxas por forma de pagamento (só admin)."""

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.caixa.models import TITULOS_FORMA
from cfauto.caixa.schemas import TaxaForma
from cfauto.caixa.taxas import atualizar_taxa, listar_taxas
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio, ValorInvalido
from cfauto.core.money import arredondar, formatar_numero
from cfauto.core.permissoes import Ator
from cfauto.ui.comum import criar_tabela, ler_decimal, mostrar_erro

_COLUNAS = ["Forma", "Taxa (%)", "Dias p/ liquidar", "Repasse ao cliente"]
_COLUNA_PCT = 1
_COLUNA_DIAS = 2
_COLUNA_REPASSE = 3


def _ler_dias(texto: str, rotulo: str) -> int:
    valor = ler_decimal(texto, rotulo)
    if valor != valor.to_integral_value():
        raise ValorInvalido(f"{rotulo}: informe um número inteiro de dias.")
    return int(valor)


def _ler_pct(texto: str, rotulo: str) -> Decimal:
    # Na precisão gravada (2 casas): "1,501" sobre 1,50 não é alteração.
    return arredondar(ler_decimal(texto, rotulo))


class PaginaParametros(QWidget):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._taxas: list[TaxaForma] = []
        self.tabela_taxas = criar_tabela(_COLUNAS)
        self.tabela_taxas.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        salvar = QPushButton("Salvar taxas")
        salvar.clicked.connect(self.salvar_taxas)
        self._mensagem = QLabel()
        botoes = QHBoxLayout()
        botoes.addWidget(salvar)
        botoes.addWidget(self._mensagem)
        botoes.addStretch()
        grupo = QGroupBox("Taxas por forma de pagamento")
        layout_grupo = QVBoxLayout(grupo)
        layout_grupo.addWidget(self.tabela_taxas)
        layout_grupo.addLayout(botoes)
        layout = QVBoxLayout(self)
        layout.addWidget(grupo)
        layout.addStretch()
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            self._taxas = listar_taxas(s, self._ator)
        tabela = self.tabela_taxas
        tabela.setRowCount(len(self._taxas))
        for linha, taxa in enumerate(self._taxas):
            forma = QTableWidgetItem(TITULOS_FORMA[taxa.forma])
            forma.setFlags(forma.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tabela.setItem(linha, 0, forma)
            tabela.setItem(linha, _COLUNA_PCT, QTableWidgetItem(formatar_numero(taxa.pct)))
            tabela.setItem(linha, _COLUNA_DIAS, QTableWidgetItem(str(taxa.dias)))
            repasse = QTableWidgetItem()
            repasse.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            repasse.setCheckState(
                Qt.CheckState.Checked if taxa.repasse else Qt.CheckState.Unchecked
            )
            tabela.setItem(linha, _COLUNA_REPASSE, repasse)
        tabela.resizeColumnsToContents()

    def _texto(self, linha: int, coluna: int) -> str:
        item = self.tabela_taxas.item(linha, coluna)
        return "" if item is None else item.text()

    def _repasse(self, linha: int) -> bool:
        item = self.tabela_taxas.item(linha, _COLUNA_REPASSE)
        return item is not None and item.checkState() == Qt.CheckState.Checked

    def salvar_taxas(self) -> None:
        self._mensagem.setText("")
        # Lê e valida todas as linhas antes de gravar: um erro não deixa gravação pela metade.
        try:
            novas: list[TaxaForma] = []
            for linha, atual in enumerate(self._taxas):
                titulo = TITULOS_FORMA[atual.forma]
                novas.append(
                    TaxaForma(
                        atual.forma,
                        _ler_pct(self._texto(linha, _COLUNA_PCT), f"{titulo} — taxa (%)"),
                        _ler_dias(self._texto(linha, _COLUNA_DIAS), f"{titulo} — dias"),
                        self._repasse(linha),
                    )
                )
            # Só o que mudou vai ao serviço: atualizar_taxa audita mesmo sem diferença.
            alteradas = [
                nova for nova, atual in zip(novas, self._taxas, strict=True) if nova != atual
            ]
            with transacao(self._fabrica) as s:
                for taxa in alteradas:
                    atualizar_taxa(s, self._ator, taxa.forma, taxa.pct, taxa.dias, taxa.repasse)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.recarregar()
        self._mensagem.setText("Taxas salvas." if alteradas else "Nenhuma alteração.")
