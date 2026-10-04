"""Textos e controles do caixa compartilhados entre o PDV, os diálogos e o Histórico."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QComboBox, QLineEdit
from sqlalchemy.orm import Session, sessionmaker

from cfauto.caixa.models import TITULOS_FORMA, FormaPagamento
from cfauto.caixa.schemas import ResumoSessao, TotaisForma
from cfauto.clientes.cadastro import buscar_clientes
from cfauto.core.db import transacao
from cfauto.core.money import formatar_brl
from cfauto.core.permissoes import Ator

CLIENTE_NAO_ENCONTRADO = "Nenhum cliente encontrado."


class _CampoBusca(QLineEdit):
    """Enter dispara a busca e não vaza para o botão padrão do diálogo que hospeda o campo."""

    def keyPressEvent(self, event: QKeyEvent) -> None:
        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()


class BuscaCliente:
    """Campo de busca de cliente (Enter) com combo para escolher entre vários resultados.

    Quem usa posiciona `campo` e `opcoes` no próprio layout; um único resultado é escolhido
    direto. `ao_escolher` recebe o id do cliente e `ao_avisar`, o aviso de busca sem resultado.
    O dono deve guardar a instância (a busca vive enquanto ele viver).
    """

    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        placeholder: str,
        *,
        ao_escolher: Callable[[int], None],
        ao_avisar: Callable[[str], None],
    ) -> None:
        self._fabrica = fabrica
        self._ator = ator
        self._ao_escolher = ao_escolher
        self._ao_avisar = ao_avisar
        self.campo = _CampoBusca()
        self.campo.setPlaceholderText(placeholder)
        self.campo.returnPressed.connect(self.buscar)
        self.opcoes = QComboBox()
        self.opcoes.hide()
        self.opcoes.activated.connect(self._escolher)

    def buscar(self) -> None:
        texto = self.campo.text().strip()
        if not texto:
            return
        with transacao(self._fabrica) as s:
            encontrados = buscar_clientes(s, self._ator, texto)
        self.opcoes.clear()
        self.opcoes.hide()
        if not encontrados:
            self._ao_avisar(CLIENTE_NAO_ENCONTRADO)
            return
        if len(encontrados) == 1:
            self.campo.clear()
            self._ao_escolher(encontrados[0].id)
            return
        for cliente in encontrados:
            self.opcoes.addItem(f"{cliente.codigo} — {cliente.nome}", cliente.id)
        self.opcoes.show()

    def limpar(self) -> None:
        self.campo.clear()
        self.opcoes.hide()

    def _escolher(self, indice: int) -> None:
        cliente_id = self.opcoes.itemData(indice)
        self.opcoes.hide()
        self.campo.clear()
        if cliente_id is not None:
            self._ao_escolher(int(cliente_id))


def _linhas_por_forma(totais: dict[FormaPagamento, TotaisForma]) -> list[str]:
    if not totais:
        return ["  nenhuma"]
    return [
        f"  {TITULOS_FORMA[forma]}: {t.qtd} · bruto {formatar_brl(t.bruto)}"
        f" · taxa {formatar_brl(t.taxa)} · líquido {formatar_brl(t.liquido)}"
        for forma, t in totais.items()
    ]


def descrever_resumo(resumo: ResumoSessao) -> str:
    linhas = ["Vendas:", *_linhas_por_forma(resumo.vendas)]
    linhas += ["Recebimentos de crediário:", *_linhas_por_forma(resumo.recebimentos)]
    if resumo.canceladas_qtd:
        linhas.append(
            f"Canceladas: {resumo.canceladas_qtd} ({formatar_brl(resumo.canceladas_bruto)},"
            " fora dos totais)"
        )
    linhas += [
        f"Total vendido: {formatar_brl(resumo.total_vendido)}",
        f"Fundo de troco: {formatar_brl(resumo.fundo_troco)}",
        f"Dinheiro recebido: {formatar_brl(resumo.dinheiro)}",
        f"Gaveta: {formatar_brl(resumo.gaveta)}",
    ]
    return "\n".join(linhas)
