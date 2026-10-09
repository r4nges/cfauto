"""Gera os recursos binários do tema em cfauto/ui/recursos.

Rode de novo só quando o logo ou os tokens mudarem; o resultado é commitado.

Uso: uv run python tools/gerar_recursos.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF

from cfauto.ui.tema.tokens import CLARO

RECURSOS = Path(__file__).resolve().parent.parent / "cfauto" / "ui" / "recursos"
LADO_SETA = 12


def gerar_seta(destino: Path, cor: str = CLARO.texto_secundario) -> None:
    """Triângulo para baixo (seta do QComboBox), 12x12 com fundo transparente."""
    imagem = QImage(LADO_SETA, LADO_SETA, QImage.Format.Format_ARGB32)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QColor(cor))
    pintor.drawPolygon(QPolygonF([QPointF(1.5, 3.5), QPointF(10.5, 3.5), QPointF(6.0, 8.5)]))
    pintor.end()
    if not imagem.save(str(destino), "PNG"):
        raise OSError(f"não consegui gravar {destino}")


def main() -> int:
    gerar_seta(RECURSOS / "seta-baixo.png")
    print(f"gerado: {RECURSOS / 'seta-baixo.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
