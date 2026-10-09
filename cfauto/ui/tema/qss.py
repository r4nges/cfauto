"""QSS do tema, gerado dos tokens. Sem literal de cor aqui: tudo vem de `${token}`."""

from dataclasses import asdict
from pathlib import Path
from string import Template

from cfauto.ui.tema.tokens import Tokens

ARQUIVO_SETA_BAIXO = Path(__file__).resolve().parent.parent / "recursos" / "seta-baixo.png"

_MODELO = Template(
    """
QMainWindow { background: ${fundo}; }
QDialog, QWizard, QWizardPage, QMessageBox { background: ${superficie}; }

QLabel[papel="titulo"] { color: ${indigo_escuro}; font-size: 13pt; font-weight: 600; }
QLabel[papel="erro"] { color: ${erro}; }
QLabel[papel="aviso"] { color: ${aviso}; }
QLabel[papel="sucesso"] { color: ${sucesso}; }

QToolBar#faixa {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 ${preto}, stop:0.4 ${indigo_escuro}, stop:1 ${indigo});
    border: none;
    padding: 4px 8px;
    spacing: 6px;
}
QToolBar#faixa QLabel { color: ${sobre_marca}; background: transparent; }
QToolBar#faixa QLabel[papel="aviso"] { color: ${aviso_sobre_marca}; font-weight: bold; }
QToolBar#faixa QToolButton {
    color: ${sobre_marca};
    background: transparent;
    border: none;
    border-radius: ${raio_controle}px;
    padding: 5px 10px;
}
QToolBar#faixa QToolButton:hover { background: ${sobre_marca_hover}; }

QFrame#lateral { background: ${superficie}; border: none; border-right: 1px solid ${linha}; }
QListWidget#navegacao { background: ${superficie}; border: none; outline: none; }
QListWidget#navegacao::item {
    color: ${texto};
    padding: 8px 14px;
    border-left: 3px solid transparent;
}
QListWidget#navegacao::item:hover { background: ${fundo}; }
QListWidget#navegacao::item:selected {
    background: ${selecao};
    color: ${indigo};
    border-left: 3px solid ${indigo};
}

QTabWidget::pane { border: 1px solid ${linha}; background: ${superficie}; }
QTabBar::tab {
    background: transparent;
    color: ${texto_secundario};
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: ${indigo}; border-bottom: 2px solid ${indigo}; }
QTabBar::tab:hover:!selected { color: ${texto}; }

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background: ${superficie};
    color: ${texto};
    border: 1px solid ${linha_campo};
    border-radius: ${raio_controle}px;
    padding: 5px 8px;
    selection-background-color: ${indigo};
    selection-color: ${sobre_marca};
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid ${indigo};
}
QAbstractSpinBox QLineEdit, QComboBox QLineEdit {
    border: none;
    background: transparent;
    padding: 0;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {
    background: ${fundo};
    color: ${texto_secundario};
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url("${seta_baixo}"); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: ${superficie};
    color: ${texto};
    border: 1px solid ${linha_campo};
    selection-background-color: ${selecao};
    selection-color: ${indigo};
    outline: none;
}

QPushButton {
    background: ${superficie};
    color: ${texto};
    border: 1px solid ${linha_campo};
    border-radius: ${raio_controle}px;
    padding: 6px 18px;
}
QPushButton:hover { border-color: ${indigo}; }
QPushButton:pressed { background: ${selecao}; }
QPushButton:disabled {
    background: ${fundo};
    color: ${texto_secundario};
    border-color: ${linha};
}
QPushButton[papel="primario"], QPushButton:default {
    background: ${indigo};
    color: ${sobre_marca};
    border: 1px solid ${indigo};
    font-weight: 600;
}
QPushButton[papel="primario"]:hover, QPushButton:default:hover { background: ${indigo_escuro}; }
QPushButton[papel="primario"]:disabled, QPushButton:default:disabled {
    background: ${linha_campo};
    border-color: ${linha_campo};
    color: ${superficie};
}
QPushButton[papel="perigo"] { color: ${perigo}; border: 1px solid ${perigo}; }
QPushButton[papel="perigo"]:hover { background: ${perigo_fundo}; }

QTableView, QTableWidget {
    background: ${superficie};
    alternate-background-color: ${zebra};
    color: ${texto};
    gridline-color: ${linha};
    border: 1px solid ${linha};
    selection-background-color: ${selecao};
    selection-color: ${texto};
}
QHeaderView { background: ${cabecalho_tabela}; border: none; }
QTableCornerButton::section { background: ${cabecalho_tabela}; border: none; }
QHeaderView::section {
    background: ${cabecalho_tabela};
    color: ${texto};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid ${linha};
    border-bottom: 1px solid ${linha};
    font-weight: 600;
}

QGroupBox {
    border: 1px solid ${linha};
    border-radius: ${raio_painel}px;
    margin-top: 12px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: ${texto_secundario};
}

QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical {
    background: ${linha_campo};
    border-radius: 4px;
    min-height: 24px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover { background: ${texto_secundario}; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal {
    background: ${linha_campo};
    border-radius: 4px;
    min-width: 24px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover { background: ${texto_secundario}; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip {
    background: ${indigo_escuro};
    color: ${sobre_marca};
    border: 1px solid ${indigo};
    padding: 4px 6px;
}
"""
)


def gerar_qss(tokens: Tokens, *, seta_baixo: Path = ARQUIVO_SETA_BAIXO) -> str:
    return _MODELO.substitute(asdict(tokens), seta_baixo=seta_baixo.as_posix())
