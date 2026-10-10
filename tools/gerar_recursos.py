"""Gera os recursos binários do tema em cfauto/ui/recursos.

Rode de novo só quando o logo ou os tokens mudarem; o resultado é commitado.

Uso: uv run python tools/gerar_recursos.py
"""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF
from PySide6.QtSvg import QSvgRenderer

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


TAMANHOS_ICONE = (16, 32, 48, 256)


def montar_ico(imagens: list[tuple[int, bytes]]) -> bytes:
    """Container .ico com uma entrada PNG por tamanho (formato aceito desde o Vista)."""
    cabecalho = struct.pack("<HHH", 0, 1, len(imagens))
    deslocamento = 6 + 16 * len(imagens)
    entradas = b""
    corpo = b""
    for lado, png in imagens:
        entradas += struct.pack(
            "<BBBBHHII", lado % 256, lado % 256, 0, 0, 1, 32, len(png), deslocamento + len(corpo)
        )
        corpo += png
    return cabecalho + entradas + corpo


def _png_do_logo(renderizador: QSvgRenderer, lado: int) -> bytes:
    imagem = QImage(lado, lado, QImage.Format.Format_ARGB32)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderizador.render(pintor)
    pintor.end()
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "PNG")
    return bytes(dados.data())


def gerar_icone(destino: Path) -> None:
    renderizador = QSvgRenderer(str(RECURSOS / "logo.svg"))
    imagens = [(lado, _png_do_logo(renderizador, lado)) for lado in TAMANHOS_ICONE]
    destino.write_bytes(montar_ico(imagens))


def main() -> int:
    gerar_seta(RECURSOS / "seta-baixo.png")
    print(f"gerado: {RECURSOS / 'seta-baixo.png'}")
    gerar_icone(RECURSOS / "icone.ico")
    print(f"gerado: {RECURSOS / 'icone.ico'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
