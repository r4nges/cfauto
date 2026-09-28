"""Aba Entradas de NF-e: importar XML, conferir item a item, ver itens e estornar."""

from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio, EstoqueInsuficiente, ValorInvalido
from cfauto.core.money import arredondar_qtd, formatar_brl, formatar_numero, formatar_qtd
from cfauto.core.permissoes import Ator
from cfauto.estoque.entrada import (
    confirmar_entrada,
    estornar_entrada,
    listar_notas,
    obter_nota,
    preparar_entrada,
)
from cfauto.estoque.models import NotaEntrada, NotaEntradaItem, Produto
from cfauto.estoque.nfe import ItemNotaLido
from cfauto.estoque.produtos import buscar_produtos
from cfauto.estoque.schemas import AcaoItem, ConferenciaNota, DecisaoItem, ItemConferencia
from cfauto.ui.comum import criar_tabela, ler_decimal, mostrar_erro, preencher_tabela

_COLUNAS_NOTAS = ["Entrada", "Nota", "Emitente", "Valor", "Itens", "Situação"]
_COLUNAS_ITENS = [
    "Nº",
    "Descrição da nota",
    "Qtd nota",
    "Custo total",
    "Produto",
    "Fator",
    "Qtd estoque",
]
_COLUNAS_CONFERENCIA = [
    "Nº",
    "Cód. forn.",
    "EAN",
    "Descrição",
    "Un.",
    "Qtd nota",
    "Custo total",
    "Ação",
    "Produto",
    "Fator",
    "Qtd estoque",
    "Custo unit.",
]
_COL_DESCRICAO = 3
_COL_ACAO = 7
_COL_PRODUTO = 8
_COL_FATOR = 9
_COL_QTD_ESTOQUE = 10
_COL_CUSTO_UNIT = 11
_TITULOS_ACAO = {
    AcaoItem.VINCULAR: "Vincular",
    AcaoItem.CRIAR: "Criar novo",
    AcaoItem.IGNORAR: "Ignorar",
}


def _celula(texto: str) -> QTableWidgetItem:
    celula = QTableWidgetItem(texto)
    celula.setFlags(celula.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return celula


@dataclass
class _EstadoItem:
    item: ItemNotaLido
    acao: AcaoItem
    produto_id: int | None
    produto_texto: str
    descricao: str
    fator_texto: str


def _estado_inicial(sugestao: ItemConferencia) -> _EstadoItem:
    item = sugestao.item
    fator = formatar_numero(sugestao.fator_sugerido, 0)
    if sugestao.produto_id is None:
        return _EstadoItem(item, AcaoItem.CRIAR, None, "", item.descricao, fator)
    texto = f"{sugestao.produto_codigo} — {sugestao.produto_descricao}"
    return _EstadoItem(item, AcaoItem.VINCULAR, sugestao.produto_id, texto, item.descricao, fator)


class DialogoEscolherProduto(QDialog):
    """Busca de produto ativo para vincular a um item da nota."""

    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._produtos: list[Produto] = []
        self.produto: Produto | None = None
        self.setWindowTitle("Escolher produto")
        self.resize(720, 420)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Código, EAN ou descrição")
        self.busca.textChanged.connect(self._filtrar)
        self.tabela = criar_tabela(["Código", "EAN", "Descrição", "Embalagem", "Fator"])
        self.tabela.doubleClicked.connect(self._duplo_clique)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.escolher)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.busca)
        layout.addWidget(self.tabela)
        layout.addWidget(botoes)
        self._filtrar()

    def _filtrar(self) -> None:
        with transacao(self._fabrica) as s:
            self._produtos = buscar_produtos(s, self._ator, self.busca.text())
        preencher_tabela(
            self.tabela,
            [
                [p.codigo, p.ean or "", p.descricao, p.embalagem, formatar_qtd(p.fator)]
                for p in self._produtos
            ],
        )

    def _duplo_clique(self, _indice: QModelIndex) -> None:
        self.escolher()

    def escolher(self) -> None:
        linha = self.tabela.currentRow()
        if 0 <= linha < len(self._produtos):
            self.produto = self._produtos[linha]
            self.accept()


class DialogoConferencia(QDialog):
    """Conferência item a item antes de lançar a nota."""

    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        conteudo: bytes,
        conferencia: ConferenciaNota,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._conteudo = conteudo
        self.nota_id: int | None = None
        nota = conferencia.nota
        self.setWindowTitle(f"Conferência da NF {nota.numero}/{nota.serie}")
        self.resize(1250, 520)
        cabecalho = QLabel(
            f"<b>{escape(nota.emitente_nome)}</b> — NF {nota.numero}/{nota.serie} — "
            f"emissão {nota.data_emissao:%d/%m/%Y} — total {formatar_brl(nota.valor_total)}"
        )
        self.avisos = QLabel("<br>".join(escape(aviso) for aviso in conferencia.avisos))
        self.avisos.setStyleSheet("color: #b9770e;")
        self.avisos.setVisible(bool(conferencia.avisos))
        self._estados = [_estado_inicial(sugestao) for sugestao in conferencia.itens]
        self._combos_acao: list[QComboBox] = []
        self._botoes_produto: list[QPushButton] = []
        self._campos_fator: list[QLineEdit] = []
        self.botao_confirmar = QPushButton("Confirmar entrada")
        self.botao_confirmar.clicked.connect(self.confirmar)
        self.tabela = QTableWidget(len(self._estados), len(_COLUNAS_CONFERENCIA))
        self.tabela.setHorizontalHeaderLabels(_COLUNAS_CONFERENCIA)
        self.tabela.verticalHeader().setVisible(False)
        self._montar_linhas()
        self.tabela.resizeColumnsToContents()
        self.tabela.itemChanged.connect(self._ao_editar_celula)

        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        rodape = QHBoxLayout()
        rodape.addStretch()
        rodape.addWidget(cancelar)
        rodape.addWidget(self.botao_confirmar)
        layout = QVBoxLayout(self)
        layout.addWidget(cabecalho)
        layout.addWidget(self.avisos)
        layout.addWidget(self.tabela)
        layout.addLayout(rodape)
        self._atualizar_confirmar()

    def _montar_linhas(self) -> None:
        for linha, estado in enumerate(self._estados):
            item = estado.item
            fixos = [
                str(item.n_item),
                item.codigo,
                item.ean or "",
                estado.descricao,
                item.unidade,
                formatar_qtd(item.qtd),
                formatar_brl(item.custo_total),
            ]
            for coluna, texto in enumerate(fixos):
                self.tabela.setItem(linha, coluna, _celula(texto))
            for coluna in (_COL_QTD_ESTOQUE, _COL_CUSTO_UNIT):
                self.tabela.setItem(linha, coluna, _celula(""))
            acao = QComboBox()
            for opcao in AcaoItem:
                acao.addItem(_TITULOS_ACAO[opcao], opcao)
            acao.setCurrentIndex(list(AcaoItem).index(estado.acao))
            acao.currentIndexChanged.connect(lambda _indice, n=linha: self._ao_mudar_acao(n))
            produto = QPushButton()
            produto.clicked.connect(lambda _marcado=False, n=linha: self._escolher_produto(n))
            fator = QLineEdit(estado.fator_texto)
            fator.textChanged.connect(lambda texto, n=linha: self._ao_mudar_fator(n, texto))
            self.tabela.setCellWidget(linha, _COL_ACAO, acao)
            self.tabela.setCellWidget(linha, _COL_PRODUTO, produto)
            self.tabela.setCellWidget(linha, _COL_FATOR, fator)
            self._combos_acao.append(acao)
            self._botoes_produto.append(produto)
            self._campos_fator.append(fator)
            self._atualizar_linha(linha)

    def _calculos(self, estado: _EstadoItem) -> tuple[str, str]:
        if estado.acao is AcaoItem.IGNORAR:
            return "—", "—"
        try:
            fator = ler_decimal(estado.fator_texto, "Fator")
        except ErroDominio:
            return "—", "—"  # fator incompleto durante a digitação
        qtd = arredondar_qtd(estado.item.qtd * fator)
        if qtd <= 0:
            return "—", "—"
        return formatar_qtd(qtd), formatar_brl(estado.item.custo_total / qtd)

    def _atualizar_linha(self, linha: int) -> None:
        estado = self._estados[linha]
        vincular = estado.acao is AcaoItem.VINCULAR
        botao = self._botoes_produto[linha]
        botao.setEnabled(vincular)
        if not vincular:
            botao.setText("—")
        elif estado.produto_id is None:
            botao.setText("Escolher…")
        else:
            botao.setText(estado.produto_texto)
        self._campos_fator[linha].setEnabled(estado.acao is not AcaoItem.IGNORAR)
        descricao = self.tabela.item(linha, _COL_DESCRICAO)
        assert descricao is not None  # sempre preenchida em _montar_linhas
        if estado.acao is AcaoItem.CRIAR:
            descricao.setFlags(descricao.flags() | Qt.ItemFlag.ItemIsEditable)
        else:
            descricao.setFlags(descricao.flags() & ~Qt.ItemFlag.ItemIsEditable)
        qtd, custo = self._calculos(estado)
        celula_qtd = self.tabela.item(linha, _COL_QTD_ESTOQUE)
        celula_custo = self.tabela.item(linha, _COL_CUSTO_UNIT)
        assert celula_qtd is not None and celula_custo is not None
        celula_qtd.setText(qtd)
        celula_custo.setText(custo)

    def _ao_mudar_acao(self, linha: int) -> None:
        self._estados[linha].acao = AcaoItem(self._combos_acao[linha].currentData())
        self._atualizar_linha(linha)
        self._atualizar_confirmar()

    def _ao_mudar_fator(self, linha: int, texto: str) -> None:
        self._estados[linha].fator_texto = texto
        self._atualizar_linha(linha)

    def _ao_editar_celula(self, celula: QTableWidgetItem) -> None:
        if celula.column() == _COL_DESCRICAO:
            self._estados[celula.row()].descricao = celula.text()

    def _escolher_produto(self, linha: int) -> None:
        dialogo = DialogoEscolherProduto(self._fabrica, self._ator, self)
        if dialogo.exec() and dialogo.produto is not None:
            self.definir_produto(linha, dialogo.produto)

    def acao_da_linha(self, linha: int) -> AcaoItem:
        return self._estados[linha].acao

    def campo_fator(self, linha: int) -> QLineEdit:
        return self._campos_fator[linha]

    def definir_acao(self, linha: int, acao: AcaoItem) -> None:
        self._combos_acao[linha].setCurrentIndex(list(AcaoItem).index(acao))

    def definir_produto(self, linha: int, produto: Produto) -> None:
        """Vincula o item ao produto escolhido; o fator passa a ser o do produto."""
        estado = self._estados[linha]
        estado.produto_id = produto.id
        estado.produto_texto = f"{produto.codigo} — {produto.descricao}"
        self.definir_acao(linha, AcaoItem.VINCULAR)
        self._campos_fator[linha].setText(formatar_numero(produto.fator, 0))
        self._atualizar_linha(linha)
        self._atualizar_confirmar()

    def pronto(self) -> bool:
        return all(
            estado.acao is not AcaoItem.VINCULAR or estado.produto_id is not None
            for estado in self._estados
        )

    def _atualizar_confirmar(self) -> None:
        self.botao_confirmar.setEnabled(self.pronto())

    def decisoes(self) -> list[DecisaoItem]:
        resultado = []
        for estado in self._estados:
            numero = estado.item.n_item
            if estado.acao is AcaoItem.IGNORAR:
                resultado.append(DecisaoItem(numero, AcaoItem.IGNORAR))
                continue
            fator = ler_decimal(estado.fator_texto, f"Fator do item {numero}")
            if estado.acao is AcaoItem.VINCULAR:
                resultado.append(
                    DecisaoItem(
                        numero, AcaoItem.VINCULAR, produto_id=estado.produto_id, fator=fator
                    )
                )
            else:
                resultado.append(
                    DecisaoItem(numero, AcaoItem.CRIAR, descricao=estado.descricao, fator=fator)
                )
        return resultado

    def confirmar(self) -> None:
        try:
            decisoes = self.decisoes()
            with transacao(self._fabrica) as s:
                self.nota_id = confirmar_entrada(s, self._ator, self._conteudo, decisoes).id
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()


def _linha_item(item: NotaEntradaItem) -> list[str]:
    produto = (
        "Ignorado" if item.produto is None else f"{item.produto.codigo} — {item.produto.descricao}"
    )
    return [
        str(item.n_item),
        item.descricao_nota,
        formatar_qtd(item.qtd_nota),
        formatar_brl(item.custo_total),
        produto,
        "" if item.fator is None else formatar_qtd(item.fator),
        "" if item.qtd_estoque is None else formatar_qtd(item.qtd_estoque),
    ]


class DialogoItensNota(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        nota_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        with transacao(fabrica) as s:
            nota = obter_nota(s, ator, nota_id)
        self.setWindowTitle(f"Itens da NF {nota.numero}/{nota.serie} — {nota.emitente_nome}")
        self.resize(900, 400)
        self.tabela = criar_tabela(_COLUNAS_ITENS)
        preencher_tabela(self.tabela, [_linha_item(item) for item in nota.itens])
        fechar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        fechar.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabela)
        layout.addWidget(fechar)


def _linha_nota(nota: NotaEntrada) -> list[str]:
    return [
        f"{nota.data_entrada:%d/%m/%Y %H:%M}",
        f"{nota.numero}/{nota.serie}",
        nota.emitente_nome,
        formatar_brl(nota.valor_total),
        str(len(nota.itens)),
        "Estornada" if nota.estornada else "Lançada",
    ]


class TelaEntradas(QWidget):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._notas: list[NotaEntrada] = []

        importar = QPushButton("Importar XML…")
        importar.clicked.connect(self._escolher_arquivo)
        itens = QPushButton("Ver itens")
        itens.clicked.connect(self._ver_itens)
        self.botao_estornar = QPushButton("Estornar")
        self.botao_estornar.clicked.connect(self._estornar_selecionada)
        self.botao_estornar.setVisible(ator.admin)
        self.tabela = criar_tabela(_COLUNAS_NOTAS)
        self.tabela.doubleClicked.connect(self._duplo_clique)

        botoes = QHBoxLayout()
        for botao in (importar, itens, self.botao_estornar):
            botoes.addWidget(botao)
        botoes.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(botoes)
        layout.addWidget(self.tabela)
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            self._notas = listar_notas(s, self._ator)
        preencher_tabela(self.tabela, [_linha_nota(nota) for nota in self._notas])

    def ids_na_tabela(self) -> list[int]:
        return [nota.id for nota in self._notas]

    def selecionar(self, linha: int) -> None:
        self.tabela.setCurrentCell(linha, 0)

    def selecionada(self) -> NotaEntrada | None:
        linha = self.tabela.currentRow()
        return self._notas[linha] if 0 <= linha < len(self._notas) else None

    def _escolher_arquivo(self) -> None:
        caminho, _filtro = QFileDialog.getOpenFileName(
            self, "Importar XML da NF-e", "", "XML da NF-e (*.xml)"
        )
        if caminho:
            self.importar_arquivo(Path(caminho))

    def importar_arquivo(self, caminho: Path) -> None:
        try:
            conteudo = caminho.read_bytes()
        except OSError as erro:
            mostrar_erro(self, ValorInvalido(f"Não foi possível ler o arquivo: {erro}"))
            return
        try:
            with transacao(self._fabrica) as s:
                conferencia = preparar_entrada(s, self._ator, conteudo)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        if DialogoConferencia(self._fabrica, self._ator, conteudo, conferencia, self).exec():
            self.recarregar()

    def _ver_itens(self) -> None:
        nota = self.selecionada()
        if nota is not None:
            DialogoItensNota(self._fabrica, self._ator, nota.id, self).exec()

    def _duplo_clique(self, _indice: QModelIndex) -> None:
        self._ver_itens()

    def _estornar_selecionada(self) -> None:
        nota = self.selecionada()
        if nota is not None:
            self.estornar_nota(nota.id, self._perguntar)

    def _perguntar(self, texto: str) -> bool:
        resposta = QMessageBox.question(self, "CFAUTO", texto)
        return resposta == QMessageBox.StandardButton.Yes

    def _estornar(self, nota_id: int, *, negativo: bool) -> None:
        with transacao(self._fabrica) as s:
            estornar_entrada(s, self._ator, nota_id, confirmar_negativo=negativo)

    def estornar_nota(self, nota_id: int, confirmar: Callable[[str], bool]) -> bool:
        """Estorna com confirmação; se o saldo ficar negativo, pede uma segunda confirmação."""
        if not confirmar("Estornar esta nota? As quantidades lançadas saem do estoque."):
            return False
        try:
            try:
                self._estornar(nota_id, negativo=False)
            except EstoqueInsuficiente as erro:
                if not confirmar(f"{erro}\n\nEstornar mesmo assim?"):
                    return False
                self._estornar(nota_id, negativo=True)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return False
        self.recarregar()
        return True
