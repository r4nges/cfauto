"""Aba Serviços do Estoque: lista e cadastro com materiais."""

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.money import formatar_brl, formatar_numero, formatar_pct
from cfauto.core.permissoes import Ator
from cfauto.estoque.models import Servico, ServicoMaterial
from cfauto.estoque.schemas import DadosMaterial, DadosServico
from cfauto.estoque.servicos import (
    atualizar_servico,
    criar_servico,
    desativar_servico,
    listar_servicos,
    reativar_servico,
)
from cfauto.ui.comum import criar_tabela, ler_decimal, mostrar_erro, preencher_tabela

_COLUNAS = ["Código", "Nome", "Materiais", "Custo materiais", "Mão de obra", "Preço"]
_COLUNAS_MATERIAIS = ["Descrição", "Custo unit.", "Qtd"]


class DialogoServico(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        servico: Servico | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._servico = servico
        self.setWindowTitle(
            "Novo serviço" if servico is None else f"Editar serviço {servico.codigo}"
        )
        self.resize(560, 420)
        self.nome = QLineEdit("" if servico is None else servico.nome)
        self.mao_obra = QLineEdit(
            "50" if servico is None else formatar_numero(servico.mao_obra_pct, 0)
        )
        self.preco_rotulo = QLabel()
        self.materiais = QTableWidget(0, len(_COLUNAS_MATERIAIS))
        self.materiais.setHorizontalHeaderLabels(_COLUNAS_MATERIAIS)
        self.materiais.horizontalHeader().setStretchLastSection(True)
        if servico is None:
            self.adicionar_material()
        else:
            for material in servico.materiais:
                self.adicionar_material(
                    material.descricao,
                    formatar_numero(material.custo_unit),
                    formatar_numero(material.qtd, 0),
                )
        self.materiais.itemChanged.connect(self._atualizar_preco)
        self.mao_obra.textChanged.connect(self._atualizar_preco)

        adicionar = QPushButton("Adicionar material")
        adicionar.clicked.connect(self._adicionar_vazio)
        remover = QPushButton("Remover material")
        remover.clicked.connect(self._remover)
        botoes_materiais = QHBoxLayout()
        botoes_materiais.addWidget(adicionar)
        botoes_materiais.addWidget(remover)
        botoes_materiais.addStretch()

        form = QFormLayout()
        form.addRow("Nome", self.nome)
        form.addRow("Mão de obra (%)", self.mao_obra)
        rodape = QFormLayout()
        rodape.addRow("Preço", self.preco_rotulo)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.salvar)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Materiais"))
        layout.addWidget(self.materiais)
        layout.addLayout(botoes_materiais)
        layout.addLayout(rodape)
        layout.addWidget(botoes)
        self._atualizar_preco()

    def adicionar_material(self, descricao: str = "", custo: str = "", qtd: str = "1") -> None:
        linha = self.materiais.rowCount()
        self.materiais.insertRow(linha)
        for coluna, texto in enumerate((descricao, custo, qtd)):
            self.materiais.setItem(linha, coluna, QTableWidgetItem(texto))
        self._atualizar_preco()

    def _adicionar_vazio(self) -> None:
        self.adicionar_material()

    def _remover(self) -> None:
        linha = self.materiais.currentRow()
        if linha >= 0:
            self.materiais.removeRow(linha)
            self._atualizar_preco()

    def _texto(self, linha: int, coluna: int) -> str:
        celula = self.materiais.item(linha, coluna)
        return "" if celula is None else celula.text().strip()

    def _dados(self) -> DadosServico:
        materiais = []
        for linha in range(self.materiais.rowCount()):
            descricao, custo, qtd = (self._texto(linha, coluna) for coluna in range(3))
            if not (descricao or custo):
                continue  # linha em branco
            materiais.append(
                DadosMaterial(
                    descricao=descricao,
                    custo_unit=ler_decimal(custo, f"Custo do material {linha + 1}"),
                    qtd=ler_decimal(qtd or "1", f"Quantidade do material {linha + 1}"),
                )
            )
        return DadosServico(
            nome=self.nome.text(),
            materiais=tuple(materiais),
            mao_obra_pct=ler_decimal(self.mao_obra.text(), "Mão de obra (%)"),
        )

    def _atualizar_preco(self) -> None:
        try:
            dados = self._dados()
        except ErroDominio:
            self.preco_rotulo.setText("—")  # valor incompleto durante a digitação
            return
        simulado = Servico(
            mao_obra_pct=dados.mao_obra_pct,
            materiais=[
                ServicoMaterial(descricao=m.descricao, custo_unit=m.custo_unit, qtd=m.qtd)
                for m in dados.materiais
            ],
        )
        self.preco_rotulo.setText(formatar_brl(simulado.preco))

    def salvar(self) -> None:
        try:
            dados = self._dados()
            with transacao(self._fabrica) as s:
                if self._servico is None:
                    criar_servico(s, self._ator, dados)
                else:
                    atualizar_servico(s, self._ator, self._servico.id, dados)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()


class TelaServicos(QWidget):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._servicos: list[Servico] = []

        self.mostrar_inativos = QCheckBox("Mostrar inativos")
        self.mostrar_inativos.toggled.connect(self.recarregar)
        novo = QPushButton("Novo")
        novo.clicked.connect(self._novo)
        editar = QPushButton("Editar")
        editar.clicked.connect(self._editar)
        self.botao_ativo = QPushButton("Desativar")
        self.botao_ativo.clicked.connect(self.alternar_ativo)
        self.tabela = criar_tabela(_COLUNAS)
        self.tabela.doubleClicked.connect(self._editar_pelo_duplo_clique)
        self.tabela.itemSelectionChanged.connect(self._atualizar_botao_ativo)

        botoes = QHBoxLayout()
        for botao in (novo, editar, self.botao_ativo):
            botoes.addWidget(botao)
        botoes.addStretch()
        botoes.addWidget(self.mostrar_inativos)
        layout = QVBoxLayout(self)
        layout.addLayout(botoes)
        layout.addWidget(self.tabela)
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            self._servicos = listar_servicos(
                s, self._ator, incluir_inativos=self.mostrar_inativos.isChecked()
            )
        preencher_tabela(
            self.tabela,
            [
                [
                    sv.codigo,
                    sv.nome,
                    str(len(sv.materiais)),
                    formatar_brl(sv.custo_materiais),
                    formatar_pct(sv.mao_obra_pct / 100),
                    formatar_brl(sv.preco),
                ]
                for sv in self._servicos
            ],
        )
        self._atualizar_botao_ativo()

    def codigos_na_tabela(self) -> list[str]:
        return [sv.codigo for sv in self._servicos]

    def servico_da_linha(self, linha: int) -> Servico:
        return self._servicos[linha]

    def selecionar(self, linha: int) -> None:
        self.tabela.setCurrentCell(linha, 0)

    def selecionado(self) -> Servico | None:
        linha = self.tabela.currentRow()
        return self._servicos[linha] if 0 <= linha < len(self._servicos) else None

    def _novo(self) -> None:
        if DialogoServico(self._fabrica, self._ator, parent=self).exec():
            self.recarregar()

    def _editar(self) -> None:
        servico = self.selecionado()
        if servico is not None and DialogoServico(self._fabrica, self._ator, servico, self).exec():
            self.recarregar()

    def _editar_pelo_duplo_clique(self, _indice: QModelIndex) -> None:
        self._editar()

    def alternar_ativo(self) -> None:
        servico = self.selecionado()
        if servico is None:
            return
        try:
            with transacao(self._fabrica) as s:
                if servico.ativo:
                    desativar_servico(s, self._ator, servico.id)
                else:
                    reativar_servico(s, self._ator, servico.id)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.recarregar()

    def _atualizar_botao_ativo(self) -> None:
        servico = self.selecionado()
        inativo = servico is not None and not servico.ativo
        self.botao_ativo.setText("Reativar" if inativo else "Desativar")
