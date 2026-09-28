"""Módulo Clientes: lista com busca, cadastro, inativação e exclusão."""

from collections.abc import Callable

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.clientes.cadastro import (
    buscar_clientes,
    excluir_cliente,
    inativar_cliente,
    obter_cliente,
    reativar_cliente,
)
from cfauto.clientes.schemas import ResumoCliente
from cfauto.clientes.validacao import formatar_celular, formatar_saldo
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.money import formatar_brl
from cfauto.core.permissoes import Ator
from cfauto.ui.clientes.dialogo_cliente import DialogoCliente
from cfauto.ui.clientes.extrato import DialogoExtrato
from cfauto.ui.clientes.lancamento import DialogoLancamento
from cfauto.ui.comum import criar_tabela, mostrar_erro, preencher_tabela

_COLUNAS = ["Código", "Nome", "Celular", "Saldo", "Disponível", "Situação"]
_COLUNA_SALDO = 3
COR_DEVEDOR = "#c0392b"


class TelaClientes(QWidget):
    def __init__(
        self, fabrica: sessionmaker[Session], ator: Ator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._clientes: list[ResumoCliente] = []

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar por nome, código, CPF ou celular")
        self.busca.textChanged.connect(self.recarregar)
        self.mostrar_inativos = QCheckBox("Mostrar inativos")
        self.mostrar_inativos.toggled.connect(self.recarregar)
        novo = QPushButton("Novo")
        novo.clicked.connect(self._novo)
        editar = QPushButton("Editar")
        editar.clicked.connect(self._editar)
        self.botao_lancamento = QPushButton("Lançamento")
        self.botao_lancamento.clicked.connect(self._abrir_lancamento)
        self.botao_extrato = QPushButton("Extrato")
        self.botao_extrato.clicked.connect(self._abrir_extrato)
        self.botao_situacao = QPushButton("Inativar")
        self.botao_situacao.clicked.connect(self.alternar_situacao)
        self.botao_excluir = QPushButton("Excluir")
        self.botao_excluir.clicked.connect(self._excluir_pelo_botao)
        # Inativar/reativar/excluir: só admin (o serviço também barra).
        self.botao_situacao.setVisible(ator.admin)
        self.botao_excluir.setVisible(ator.admin)
        self.tabela = criar_tabela(_COLUNAS)
        self.tabela.doubleClicked.connect(self._editar_pelo_duplo_clique)
        self.tabela.itemSelectionChanged.connect(self._atualizar_botao_situacao)

        self._botoes = QHBoxLayout()
        for botao in (
            novo,
            editar,
            self.botao_lancamento,
            self.botao_extrato,
            self.botao_situacao,
            self.botao_excluir,
        ):
            self._botoes.addWidget(botao)
        self._botoes.addStretch()
        self._botoes.addWidget(self.mostrar_inativos)
        layout = QVBoxLayout(self)
        layout.addWidget(self.busca)
        layout.addLayout(self._botoes)
        layout.addWidget(self.tabela)
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            self._clientes = buscar_clientes(
                s,
                self._ator,
                self.busca.text(),
                incluir_inativos=self.mostrar_inativos.isChecked(),
            )
        preencher_tabela(
            self.tabela,
            [
                [
                    c.codigo,
                    c.nome,
                    formatar_celular(c.celular),
                    formatar_saldo(c.saldo_devedor),
                    "Ilimitado" if c.disponivel is None else formatar_brl(c.disponivel),
                    "Ativo" if c.ativo else "Inativo",
                ]
                for c in self._clientes
            ],
        )
        for linha, cliente in enumerate(self._clientes):
            if cliente.saldo_devedor > 0:
                item = self.tabela.item(linha, _COLUNA_SALDO)
                if item is not None:
                    item.setForeground(QColor(COR_DEVEDOR))
        self._atualizar_botao_situacao()

    def codigos_na_tabela(self) -> list[str]:
        return [c.codigo for c in self._clientes]

    def selecionar(self, linha: int) -> None:
        self.tabela.setCurrentCell(linha, 0)

    def selecionado(self) -> ResumoCliente | None:
        linha = self.tabela.currentRow()
        return self._clientes[linha] if 0 <= linha < len(self._clientes) else None

    def _novo(self) -> None:
        if DialogoCliente(self._fabrica, self._ator, parent=self).exec():
            self.recarregar()

    def _editar(self) -> None:
        cliente = self.selecionado()
        if cliente is None:
            return
        with transacao(self._fabrica) as s:
            ficha = obter_cliente(s, self._ator, cliente.id)
        if DialogoCliente(self._fabrica, self._ator, ficha, self).exec():
            self.recarregar()

    def _editar_pelo_duplo_clique(self, _indice: QModelIndex) -> None:
        self._editar()

    def alternar_situacao(self) -> None:
        cliente = self.selecionado()
        if cliente is None:
            return
        try:
            with transacao(self._fabrica) as s:
                if cliente.ativo:
                    inativar_cliente(s, self._ator, cliente.id)
                else:
                    reativar_cliente(s, self._ator, cliente.id)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.recarregar()

    def _perguntar(self, texto: str) -> bool:
        resposta = QMessageBox.question(self, "CFAUTO", texto)
        return resposta == QMessageBox.StandardButton.Yes

    def _excluir_pelo_botao(self) -> None:
        self.excluir_selecionado(self._perguntar)

    def excluir_selecionado(self, confirmar: Callable[[str], bool]) -> None:
        cliente = self.selecionado()
        if cliente is None:
            return
        texto = f"Excluir o cliente {cliente.codigo} — {cliente.nome}? Não dá para desfazer."
        if not confirmar(texto):
            return
        try:
            with transacao(self._fabrica) as s:
                excluir_cliente(s, self._ator, cliente.id)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.recarregar()

    def _atualizar_botao_situacao(self) -> None:
        cliente = self.selecionado()
        inativo = cliente is not None and not cliente.ativo
        self.botao_situacao.setText("Reativar" if inativo else "Inativar")

    def _abrir_lancamento(self) -> None:
        cliente = self.selecionado()
        if (
            cliente is not None
            and DialogoLancamento(self._fabrica, self._ator, cliente, self).exec()
        ):
            self.recarregar()

    def _abrir_extrato(self) -> None:
        cliente = self.selecionado()
        if cliente is not None:
            DialogoExtrato(self._fabrica, self._ator, cliente.id, self).exec()
