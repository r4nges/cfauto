import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, Qt, QTranslator
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from cfauto.ui.tema.qss import ARQUIVO_SETA_BAIXO, gerar_qss
from cfauto.ui.tema.tokens import CLARO, Tokens

log = logging.getLogger("cfauto.ui")
RECURSOS = Path(__file__).resolve().parent.parent / "recursos"
ARQUIVO_TRADUCAO = "qtbase_pt_BR.qm"
ARQUIVO_ICONE = RECURSOS / "icone.ico"
_tradutor: QTranslator | None = None


def _paleta(t: Tokens) -> QPalette:
    paleta = QPalette(QColor(t.superficie))
    cores = {
        QPalette.ColorRole.Window: t.superficie,
        QPalette.ColorRole.WindowText: t.texto,
        QPalette.ColorRole.Base: t.superficie,
        QPalette.ColorRole.AlternateBase: t.zebra,
        QPalette.ColorRole.Text: t.texto,
        QPalette.ColorRole.Button: t.superficie,
        QPalette.ColorRole.ButtonText: t.texto,
        QPalette.ColorRole.Highlight: t.indigo,
        QPalette.ColorRole.HighlightedText: t.sobre_marca,
        QPalette.ColorRole.PlaceholderText: t.texto_secundario,
        QPalette.ColorRole.ToolTipBase: t.indigo_escuro,
        QPalette.ColorRole.ToolTipText: t.sobre_marca,
    }
    for papel, cor in cores.items():
        paleta.setColor(papel, QColor(cor))
    for papel in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        paleta.setColor(QPalette.ColorGroup.Disabled, papel, QColor(t.texto_secundario))
    return paleta


def _pastas_traducao() -> list[Path]:
    return [Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)), RECURSOS]


def _instalar_traducao(qapp: QApplication) -> None:
    global _tradutor
    if _tradutor is not None:
        qapp.removeTranslator(_tradutor)
        _tradutor = None
    for pasta in _pastas_traducao():
        tradutor = QTranslator(qapp)
        if tradutor.load(ARQUIVO_TRADUCAO, str(pasta)):
            qapp.installTranslator(tradutor)
            _tradutor = tradutor
            return
    log.warning("%s não encontrado; os botões do Qt ficam em inglês", ARQUIVO_TRADUCAO)


def _aplicar_folha(qapp: QApplication, tokens: Tokens) -> None:
    """Aplica o QSS. Sem a seta do combo o app abre mesmo assim: só o combo perde a seta."""
    if not ARQUIVO_SETA_BAIXO.is_file():
        log.warning("%s não encontrado; os combos ficam sem a seta", ARQUIVO_SETA_BAIXO.name)
    qapp.setStyleSheet(gerar_qss(tokens, seta_baixo=ARQUIVO_SETA_BAIXO))


def _instalar_icone(qapp: QApplication) -> None:
    icone = QIcon(str(ARQUIVO_ICONE))
    if icone.isNull():
        raise FileNotFoundError(f"ícone do app ausente ou ilegível: {ARQUIVO_ICONE}")
    qapp.setWindowIcon(icone)


def aplicar_tema(qapp: QApplication, tokens: Tokens = CLARO) -> None:
    """Aplica o tema na aplicação. Cada passo falho é logado e não impede os seguintes."""
    passos: list[tuple[str, Callable[[], object]]] = [
        ("esquema de cor", lambda: qapp.styleHints().setColorScheme(Qt.ColorScheme.Light)),
        ("estilo Fusion", lambda: qapp.setStyle("Fusion")),
        ("paleta", lambda: qapp.setPalette(_paleta(tokens))),
        ("fonte", lambda: qapp.setFont(QFont(tokens.fonte_familia, tokens.fonte_pt))),
        ("folha de estilo", lambda: _aplicar_folha(qapp, tokens)),
        ("tradução", lambda: _instalar_traducao(qapp)),
        ("ícone", lambda: _instalar_icone(qapp)),
    ]
    for nome, passo in passos:
        try:
            passo()
        except Exception:
            log.exception("tema: falha ao aplicar %s", nome)
