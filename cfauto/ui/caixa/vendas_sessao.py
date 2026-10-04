"""Vendas da sessão aberta, com cancelamento (admin logado ou autorização por senha)."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.caixa.models import TITULOS_FORMA, TITULOS_TIPO_VENDA
from cfauto.caixa.schemas import LinhaVenda
from cfauto.caixa.venda import cancelar_venda, vendas_da_sessao
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio, ValorInvalido
from cfauto.core.money import formatar_brl
from cfauto.core.permissoes import Ator
from cfauto.ui.caixa.autorizacao import Autorizar, pedir_autorizacao
from cfauto.ui.comum import criar_tabela, mostrar_erro, preencher_tabela

_COLUNAS = ["Nº", "Hora", "Tipo", "Descrição", "Cliente", "Forma", "Total", "Situação"]


class DialogoVendasSessao(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        parent: QWidget | None = None,
        *,
        autorizar: Autorizar | None = None,
        pedir_motivo: Callable[[], str | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._autorizar: Autorizar = autorizar or self._autorizar_padrao
        self._pedir_motivo: Callable[[], str | None] = pedir_motivo or self._pedir_motivo_padrao
        self._linhas: list[LinhaVenda] = []
        self.setWindowTitle("Vendas da sessão")
        self.resize(820, 420)
        self.tabela = criar_tabela(_COLUNAS)
        cancelar = QPushButton("Cancelar venda")
        cancelar.clicked.connect(self.cancelar_selecionada)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        # Sem botão padrão: Enter na tabela não pode disparar o cancelamento da venda.
        cancelar.setAutoDefault(False)
        fechar.setAutoDefault(False)
        botoes = QHBoxLayout()
        botoes.addWidget(cancelar)
        botoes.addStretch()
        botoes.addWidget(fechar)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabela)
        layout.addLayout(botoes)
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            self._linhas = vendas_da_sessao(s, self._ator)
        preencher_tabela(
            self.tabela,
            [
                [
                    str(v.id),
                    f"{v.data_hora:%H:%M}",
                    TITULOS_TIPO_VENDA[v.tipo],
                    v.descricao,
                    v.cliente or "",
                    TITULOS_FORMA[v.forma],
                    formatar_brl(v.cobrado),
                    "Cancelada" if v.cancelada else "Ativa",
                ]
                for v in self._linhas
            ],
        )

    def cancelar_selecionada(self) -> None:
        linha = self.tabela.currentRow()
        if not 0 <= linha < len(self._linhas):
            return
        venda = self._linhas[linha]
        if venda.cancelada:
            mostrar_erro(self, ValorInvalido("Esta venda já está cancelada."))
            return
        motivo = self._pedir_motivo()
        if motivo is None:
            return
        if not motivo.strip():  # antes de pedir a senha do admin à toa
            mostrar_erro(self, ValorInvalido("Informe o motivo do cancelamento."))
            return
        autorizador: Ator | None = None
        if not self._ator.admin:
            autorizador = self._autorizar(
                f"Cancelar a venda nº {venda.id} ({formatar_brl(venda.cobrado)}): "
                "autorização do administrador."
            )
            if autorizador is None:
                return
        try:
            with transacao(self._fabrica) as s:
                cancelar_venda(s, self._ator, venda.id, motivo, autorizador=autorizador)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.recarregar()
        self.tabela.setCurrentCell(linha, 0)

    def _autorizar_padrao(self, texto: str) -> Ator | None:
        return pedir_autorizacao(self._fabrica, self, texto)

    def _pedir_motivo_padrao(self) -> str | None:
        texto, ok = QInputDialog.getText(self, "Cancelar venda", "Motivo do cancelamento:")
        return texto if ok else None
