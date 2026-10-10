"""Aba Produtos do Estoque: lista, cadastro, ajuste de estoque e movimentações."""

from decimal import Decimal

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.money import arredondar, formatar_brl, formatar_numero, formatar_pct, formatar_qtd
from cfauto.core.permissoes import Ator
from cfauto.estoque.models import (
    TITULOS_DESTINO,
    TITULOS_MOTIVO,
    TITULOS_TIPO_MOVIMENTO,
    Destino,
    MotivoAjuste,
    Produto,
)
from cfauto.estoque.produtos import (
    ajustar_estoque,
    atualizar_produto,
    buscar_produtos,
    categorias_usadas,
    criar_produto,
    desativar_produto,
    listar_movimentos,
    reativar_produto,
)
from cfauto.estoque.schemas import DadosProduto, LinhaMovimento
from cfauto.ui.comum import (
    criar_tabela,
    ler_decimal,
    ler_decimal_opcional,
    mostrar_erro,
    preencher_tabela,
)
from cfauto.ui.tema import CLARO

_COLUNAS = [
    "Código",
    "EAN",
    "Descrição",
    "Categoria",
    "Embalagem",
    "Estoque",
    "Custo unit.",
    "Preço venda",
    "Margem",
    "Última entrada",
    "Destino",
]
_COLUNAS_MOVIMENTOS = [
    "Data/hora",
    "Tipo",
    "Quantidade",
    "Saldo",
    "Usuário",
    "Motivo / observação",
    "Nota",
]
_COR_ABAIXO_DO_MINIMO = QColor(CLARO.perigo_fundo)
_COR_INATIVO = QColor(CLARO.texto_secundario)
_SALVAR_CANCELAR = QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel


def _linha_produto(p: Produto) -> list[str]:
    margem = p.margem
    return [
        p.codigo,
        p.ean or "",
        p.descricao,
        p.categoria,
        p.embalagem,
        formatar_qtd(p.estoque),
        formatar_brl(p.preco_fracionado),
        formatar_brl(p.preco_venda),
        "—" if margem is None else formatar_pct(margem),
        "" if p.data_ult_entrada is None else f"{p.data_ult_entrada:%d/%m/%Y}",
        TITULOS_DESTINO[p.destino],
    ]


def _texto_motivo(m: LinhaMovimento) -> str:
    partes = ["" if m.motivo is None else TITULOS_MOTIVO[m.motivo], m.observacao or ""]
    return " — ".join(parte for parte in partes if parte)


class DialogoProduto(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        produto: Produto | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._produto = produto
        self.produto_salvo: Produto | None = None
        self.setWindowTitle(
            "Novo produto" if produto is None else f"Editar produto {produto.codigo}"
        )
        with transacao(fabrica) as s:
            categorias = categorias_usadas(s, ator)

        self.descricao = QLineEdit("" if produto is None else produto.descricao)
        self.ean = QLineEdit("" if produto is None else (produto.ean or ""))
        self.categoria = QComboBox()
        self.categoria.setEditable(True)
        self.categoria.addItems(categorias)
        self.categoria.setCurrentText("" if produto is None else produto.categoria)
        self.embalagem = QLineEdit("Unidade" if produto is None else produto.embalagem)
        self.fator = QLineEdit("1" if produto is None else formatar_numero(produto.fator, 0))
        self.preco_entrada = QLineEdit(
            "0,00" if produto is None else formatar_numero(produto.preco_entrada)
        )
        self.preco_venda = QLineEdit(
            "0,00" if produto is None else formatar_numero(produto.preco_venda)
        )
        promocional = None if produto is None else produto.preco_promocional
        self.preco_promocional = QLineEdit(
            "" if promocional is None else formatar_numero(promocional)
        )
        self.preco_promocional.setPlaceholderText("sem promoção")
        self.estoque_minimo = QLineEdit(
            "0" if produto is None else formatar_numero(produto.estoque_minimo, 0)
        )
        self.minimo_manual = QCheckBox("Definido manualmente (o cálculo automático não altera)")
        self.minimo_manual.setChecked(produto is not None and produto.estoque_minimo_manual)
        self.estoque_minimo.textEdited.connect(self._minimo_editado)
        self.destino = QComboBox()
        for destino in Destino:
            self.destino.addItem(TITULOS_DESTINO[destino], destino)
        if produto is not None:
            self.destino.setCurrentIndex(list(Destino).index(produto.destino))
        self.estoque_inicial = QLineEdit("0")
        self.fracionado_rotulo = QLabel()
        # Markup % sobre o custo por unidade; o preço de venda é a fonte da verdade (não grava).
        self.markup = QLineEdit()
        self.markup.textEdited.connect(self._markup_editado)
        self._markup_em_edicao = False
        self.margem_rotulo = QLabel()
        for campo in (self.fator, self.preco_entrada, self.preco_venda):
            campo.textChanged.connect(self._atualizar_calculos)

        form = QFormLayout()
        form.addRow("Descrição", self.descricao)
        form.addRow("EAN", self.ean)
        form.addRow("Categoria", self.categoria)
        form.addRow("Embalagem", self.embalagem)
        form.addRow("Fator (unidades por embalagem)", self.fator)
        form.addRow("Preço de entrada (embalagem)", self.preco_entrada)
        form.addRow("Custo por unidade", self.fracionado_rotulo)
        form.addRow("Preço de venda", self.preco_venda)
        form.addRow("Markup (%)", self.markup)
        form.addRow("Margem", self.margem_rotulo)
        form.addRow("Preço promocional", self.preco_promocional)
        form.addRow("Estoque mínimo", self.estoque_minimo)
        form.addRow("", self.minimo_manual)
        form.addRow("Destino", self.destino)
        if produto is None:
            form.addRow("Estoque inicial", self.estoque_inicial)
        else:
            atual = QLabel(f"{formatar_qtd(produto.estoque)} (use Ajustar estoque)")
            form.addRow("Estoque atual", atual)

        botoes = QDialogButtonBox(_SALVAR_CANCELAR)
        botoes.accepted.connect(self.salvar)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botoes)
        self._atualizar_calculos()

    def _minimo_editado(self, _texto: str) -> None:
        self.minimo_manual.setChecked(True)

    def _atualizar_calculos(self) -> None:
        self._atualizar_custo_e_margem()
        # Enquanto a pessoa digita o markup, ele não é reescrito a partir do preço que calculou.
        if not self._markup_em_edicao:
            self._atualizar_markup()

    def _atualizar_custo_e_margem(self) -> None:
        try:
            simulado: Produto | None = Produto(
                fator=ler_decimal(self.fator.text(), "Fator"),
                preco_entrada=ler_decimal(self.preco_entrada.text(), "Preço de entrada"),
                preco_venda=ler_decimal(self.preco_venda.text(), "Preço de venda"),
            )
        except ErroDominio:
            simulado = None  # valor incompleto durante a digitação: só não mostra o cálculo
        if simulado is None or simulado.fator <= 0:
            self.fracionado_rotulo.setText("—")
            self.margem_rotulo.setText("—")
            return
        self.fracionado_rotulo.setText(formatar_brl(simulado.preco_fracionado))
        margem = simulado.margem
        self.margem_rotulo.setText("—" if margem is None else formatar_pct(margem))

    def _custo_unitario(self) -> Decimal | None:
        """Custo por unidade; None enquanto fator ou preço de entrada não permitem calcular."""
        try:
            fator = ler_decimal(self.fator.text(), "Fator")
            entrada = ler_decimal(self.preco_entrada.text(), "Preço de entrada")
        except ErroDominio:
            return None
        return entrada / fator if fator > 0 and entrada > 0 else None

    def _atualizar_markup(self) -> None:
        custo = self._custo_unitario()
        self.markup.setEnabled(custo is not None)
        if custo is None:
            self.markup.setText("—")
            return
        try:
            venda = ler_decimal(self.preco_venda.text(), "Preço de venda")
        except ErroDominio:
            venda = Decimal(0)
        # Sem preço ainda: campo vazio, esperando o markup para calcular o preço.
        self.markup.setText(
            "" if venda <= 0 else formatar_numero(arredondar((venda / custo - 1) * 100))
        )

    def _markup_editado(self, texto: str) -> None:
        custo = self._custo_unitario()
        if custo is None:
            return
        try:
            pct = ler_decimal(texto, "Markup")
        except ErroDominio:
            return  # incompleto durante a digitação
        preco = arredondar(custo * (1 + pct / 100))
        if preco < 0:
            return
        self._markup_em_edicao = True
        try:
            self.preco_venda.setText(formatar_numero(preco))
        finally:
            self._markup_em_edicao = False

    def _dados(self) -> DadosProduto:
        return DadosProduto(
            descricao=self.descricao.text(),
            ean=self.ean.text(),
            categoria=self.categoria.currentText(),
            embalagem=self.embalagem.text(),
            fator=ler_decimal(self.fator.text(), "Fator"),
            preco_entrada=ler_decimal(self.preco_entrada.text(), "Preço de entrada"),
            preco_venda=ler_decimal(self.preco_venda.text(), "Preço de venda"),
            preco_promocional=ler_decimal_opcional(
                self.preco_promocional.text(), "Preço promocional"
            ),
            estoque_minimo=ler_decimal(self.estoque_minimo.text(), "Estoque mínimo"),
            estoque_minimo_manual=self.minimo_manual.isChecked(),
            destino=Destino(self.destino.currentData()),
            estoque_inicial=ler_decimal(self.estoque_inicial.text(), "Estoque inicial"),
        )

    def salvar(self) -> None:
        try:
            dados = self._dados()
            with transacao(self._fabrica) as s:
                if self._produto is None:
                    self.produto_salvo = criar_produto(s, self._ator, dados)
                else:
                    self.produto_salvo = atualizar_produto(s, self._ator, self._produto.id, dados)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()


class DialogoAjusteEstoque(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        produto: Produto,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._produto = produto
        self.setWindowTitle(f"Ajustar estoque — {produto.codigo}")
        self.nova_quantidade = QLineEdit(formatar_numero(produto.estoque, 0))
        self.motivo = QComboBox()
        for motivo in MotivoAjuste:
            self.motivo.addItem(TITULOS_MOTIVO[motivo], motivo)
        self.observacao = QLineEdit()
        form = QFormLayout()
        form.addRow("Produto", QLabel(f"{produto.codigo} — {produto.descricao}"))
        form.addRow("Estoque atual", QLabel(formatar_qtd(produto.estoque)))
        form.addRow("Nova quantidade", self.nova_quantidade)
        form.addRow("Motivo", self.motivo)
        form.addRow("Observação", self.observacao)
        botoes = QDialogButtonBox(_SALVAR_CANCELAR)
        botoes.accepted.connect(self.salvar)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botoes)

    def salvar(self) -> None:
        try:
            nova = ler_decimal(self.nova_quantidade.text(), "Nova quantidade")
            with transacao(self._fabrica) as s:
                ajustar_estoque(
                    s,
                    self._ator,
                    self._produto.id,
                    nova,
                    MotivoAjuste(self.motivo.currentData()),
                    self.observacao.text(),
                )
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()


class DialogoMovimentos(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        produto: Produto,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Movimentações — {produto.codigo} {produto.descricao}")
        self.resize(900, 420)
        with transacao(fabrica) as s:
            self.linhas = listar_movimentos(s, ator, produto.id)
        self.tabela = criar_tabela(_COLUNAS_MOVIMENTOS)
        preencher_tabela(
            self.tabela,
            [
                [
                    f"{m.data_hora:%d/%m/%Y %H:%M}",
                    TITULOS_TIPO_MOVIMENTO[m.tipo],
                    formatar_qtd(m.quantidade),
                    formatar_qtd(m.saldo_apos),
                    m.usuario_nome,
                    _texto_motivo(m),
                    m.nota or "",
                ]
                for m in self.linhas
            ],
        )
        fechar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        fechar.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabela)
        layout.addWidget(fechar)


class TelaProdutos(QWidget):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._produtos: list[Produto] = []

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar por código, EAN ou descrição")
        self.busca.textChanged.connect(self.recarregar)
        self.mostrar_inativos = QCheckBox("Mostrar inativos")
        self.mostrar_inativos.toggled.connect(self.recarregar)
        novo = QPushButton("Novo")
        novo.clicked.connect(self._novo)
        editar = QPushButton("Editar")
        editar.clicked.connect(self._editar)
        ajustar = QPushButton("Ajustar estoque")
        ajustar.clicked.connect(self._ajustar)
        movimentos = QPushButton("Movimentações")
        movimentos.clicked.connect(self._movimentos)
        self.botao_ativo = QPushButton("Desativar")
        self.botao_ativo.clicked.connect(self.alternar_ativo)
        self.tabela = criar_tabela(_COLUNAS)
        self.tabela.doubleClicked.connect(self._editar_pelo_duplo_clique)
        self.tabela.itemSelectionChanged.connect(self._atualizar_botao_ativo)

        barra = QHBoxLayout()
        barra.addWidget(self.busca, 1)
        barra.addWidget(self.mostrar_inativos)
        botoes = QHBoxLayout()
        for botao in (novo, editar, ajustar, movimentos, self.botao_ativo):
            botoes.addWidget(botao)
        botoes.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(barra)
        layout.addLayout(botoes)
        layout.addWidget(self.tabela)
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            self._produtos = buscar_produtos(
                s,
                self._ator,
                self.busca.text(),
                incluir_inativos=self.mostrar_inativos.isChecked(),
            )
        preencher_tabela(self.tabela, [_linha_produto(p) for p in self._produtos])
        for linha, p in enumerate(self._produtos):
            if not p.ativo:
                self._pintar(linha, frente=_COR_INATIVO)
            elif p.estoque_minimo > 0 and p.estoque <= p.estoque_minimo:
                self._pintar(linha, fundo=_COR_ABAIXO_DO_MINIMO)
        self._atualizar_botao_ativo()

    def _pintar(
        self, linha: int, *, frente: QColor | None = None, fundo: QColor | None = None
    ) -> None:
        for coluna in range(self.tabela.columnCount()):
            celula = self.tabela.item(linha, coluna)
            if celula is None:
                continue
            if frente is not None:
                celula.setForeground(frente)
            if fundo is not None:
                celula.setBackground(fundo)

    def codigos_na_tabela(self) -> list[str]:
        return [p.codigo for p in self._produtos]

    def selecionar(self, linha: int) -> None:
        self.tabela.setCurrentCell(linha, 0)

    def selecionado(self) -> Produto | None:
        linha = self.tabela.currentRow()
        return self._produtos[linha] if 0 <= linha < len(self._produtos) else None

    def _novo(self) -> None:
        if DialogoProduto(self._fabrica, self._ator, parent=self).exec():
            self.recarregar()

    def _editar(self) -> None:
        produto = self.selecionado()
        if produto is not None and DialogoProduto(self._fabrica, self._ator, produto, self).exec():
            self.recarregar()

    def _editar_pelo_duplo_clique(self, _indice: QModelIndex) -> None:
        self._editar()

    def _ajustar(self) -> None:
        produto = self.selecionado()
        if (
            produto is not None
            and DialogoAjusteEstoque(self._fabrica, self._ator, produto, self).exec()
        ):
            self.recarregar()

    def _movimentos(self) -> None:
        produto = self.selecionado()
        if produto is not None:
            DialogoMovimentos(self._fabrica, self._ator, produto, self).exec()

    def alternar_ativo(self) -> None:
        produto = self.selecionado()
        if produto is None:
            return
        try:
            with transacao(self._fabrica) as s:
                if produto.ativo:
                    desativar_produto(s, self._ator, produto.id)
                else:
                    reativar_produto(s, self._ator, produto.id)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.recarregar()

    def _atualizar_botao_ativo(self) -> None:
        produto = self.selecionado()
        inativo = produto is not None and not produto.ativo
        self.botao_ativo.setText("Reativar" if inativo else "Desativar")
