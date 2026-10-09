import re
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cfauto.core.errors import ErroDominio, ValorInvalido
from cfauto.core.money import para_decimal


class PaginaEmConstrucao(QWidget):
    def __init__(self, titulo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        rotulo = QLabel(f"<h2>{titulo}</h2><p>Módulo em construção.</p>")
        rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(rotulo)


def mostrar_erro(parent: QWidget | None, erro: Exception) -> None:
    if isinstance(erro, ErroDominio):
        QMessageBox.warning(parent, "CFAUTO", str(erro))
    else:
        QMessageBox.critical(parent, "CFAUTO", f"Erro inesperado: {erro}")


def criar_tabela(colunas: list[str]) -> QTableWidget:
    """Tabela só leitura, com seleção de uma linha inteira."""
    tabela = QTableWidget(0, len(colunas))
    tabela.setHorizontalHeaderLabels(colunas)
    tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tabela.horizontalHeader().setStretchLastSection(True)
    tabela.verticalHeader().setVisible(False)
    return tabela


def preencher_tabela(tabela: QTableWidget, linhas: list[list[str]]) -> None:
    tabela.clearSelection()
    tabela.setRowCount(len(linhas))
    for i, valores in enumerate(linhas):
        for j, valor in enumerate(valores):
            tabela.setItem(i, j, QTableWidgetItem(valor))
    tabela.resizeColumnsToContents()


_SO_DIGITOS_E_BARRAS = re.compile(r"[\d/]*")


def formatar_data_digitada(texto: str) -> str:
    """Põe as barras de dd/mm/aaaa conforme se digita: '1503' → '15/03'.

    Sem barra sobrando no fim (senão o Backspace não anda); texto com outros caracteres,
    como uma data ISO colada, fica como está.
    """
    if not _SO_DIGITOS_E_BARRAS.fullmatch(texto):
        return texto
    digitos = "".join(c for c in texto if c.isdigit())[:8]
    partes = (digitos[:2], digitos[2:4], digitos[4:])
    return "/".join(parte for parte in partes if parte)


def aplicar_mascara_data(campo: QLineEdit) -> None:
    """Formata o campo como dd/mm/aaaa enquanto a pessoa digita, mantendo o cursor."""

    def formatar(texto: str) -> None:
        novo = formatar_data_digitada(texto)
        if novo == texto:
            return
        digitos_antes = sum(c.isdigit() for c in texto[: campo.cursorPosition()])
        campo.setText(novo)
        posicao = 0
        for i, caractere in enumerate(novo, start=1):
            if digitos_antes == 0:
                break
            if caractere.isdigit():
                digitos_antes -= 1
                posicao = i
        campo.setCursorPosition(posicao)

    campo.textEdited.connect(formatar)


_NOTACAO_CIENTIFICA = re.compile(r"[eE]")
# Nenhum campo do app precisa de mais que 10 dígitos inteiros; acima disso o valor não cabe
# em DecimalEscalado (coluna INTEGER do SQLite) e estouraria como OverflowError só na gravação.
_TETO_VALOR = Decimal(10) ** 10


def ler_decimal(texto: str, rotulo: str) -> Decimal:
    """Texto digitado (formato brasileiro) → Decimal; o erro já traz o nome do campo.

    Rejeita notação científica (o formato esperado é o brasileiro, ex. "1.234,56") e valores
    grandes demais para as colunas de dinheiro/quantidade do banco.
    """
    if _NOTACAO_CIENTIFICA.search(texto):
        raise ValorInvalido(f"{rotulo}: não use notação científica.")
    try:
        valor = para_decimal(texto)
    except ValorInvalido as erro:
        raise ValorInvalido(f"{rotulo}: {erro}") from erro
    if abs(valor) >= _TETO_VALOR:
        raise ValorInvalido(f"{rotulo}: valor grande demais.")
    return valor


def ler_decimal_opcional(texto: str, rotulo: str) -> Decimal | None:
    return None if not texto.strip() else ler_decimal(texto, rotulo)
