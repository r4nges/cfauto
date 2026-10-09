from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget

from cfauto.ui.tema.tokens import CLARO, Tokens

ARQUIVO_LOGO = Path(__file__).resolve().parent.parent / "recursos" / "logo.svg"
LARGURA_PAINEL = 210
LADO_LOGO = 104
NOME = "CFAUTO"
SLOGAN = "O SEU CFO AUTOMÁTICO"
_ESPACO_LOGO_NOME = 14
_ESPACO_NOME_SLOGAN = 4


def desenhar_marca(pintor: QPainter, largura: float, altura: float, tokens: Tokens = CLARO) -> None:
    """Fundo em gradiente, logo, nome e slogan; compartilhado pelo painel e pelo pixmap."""
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    gradiente = QLinearGradient(0, 0, largura * 0.5, altura)
    gradiente.setColorAt(0.0, QColor(tokens.preto))
    gradiente.setColorAt(0.45, QColor(tokens.indigo_escuro))
    gradiente.setColorAt(1.0, QColor(tokens.indigo))
    pintor.fillRect(QRectF(0, 0, largura, altura), gradiente)

    fonte_nome = QFont(tokens.fonte_familia, 14, QFont.Weight.Bold)
    fonte_nome.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
    fonte_slogan = QFont(tokens.fonte_familia, 8)
    fonte_slogan.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
    altura_nome = QFontMetrics(fonte_nome).height()
    altura_slogan = QFontMetrics(fonte_slogan).height()
    bloco = LADO_LOGO + _ESPACO_LOGO_NOME + altura_nome + _ESPACO_NOME_SLOGAN + altura_slogan
    topo = (altura - bloco) / 2

    logo = QSvgRenderer(str(ARQUIVO_LOGO))
    logo.render(pintor, QRectF((largura - LADO_LOGO) / 2, topo, LADO_LOGO, LADO_LOGO))

    y = topo + LADO_LOGO + _ESPACO_LOGO_NOME
    pintor.setPen(QColor(tokens.sobre_marca))
    pintor.setFont(fonte_nome)
    pintor.drawText(QRectF(0, y, largura, altura_nome), Qt.AlignmentFlag.AlignHCenter, NOME)
    y += altura_nome + _ESPACO_NOME_SLOGAN
    cor_slogan = QColor(tokens.sobre_marca)
    cor_slogan.setAlphaF(0.85)
    pintor.setPen(cor_slogan)
    pintor.setFont(fonte_slogan)
    pintor.drawText(QRectF(0, y, largura, altura_slogan), Qt.AlignmentFlag.AlignHCenter, SLOGAN)


def pixmap_marca(largura: int, altura: int, tokens: Tokens = CLARO) -> QPixmap:
    pixmap = QPixmap(largura, altura)
    pintor = QPainter(pixmap)
    try:
        desenhar_marca(pintor, largura, altura, tokens)
    finally:
        pintor.end()
    return pixmap


class PainelMarca(QFrame):
    """Coluna de marca dos diálogos de entrada. Só desenha; não tem lógica."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(LARGURA_PAINEL)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def paintEvent(self, evento: QPaintEvent) -> None:  # noqa: N802 - API do Qt
        pintor = QPainter(self)
        try:
            desenhar_marca(pintor, self.width(), self.height())
        finally:
            pintor.end()
