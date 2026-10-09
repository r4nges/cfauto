from pathlib import Path

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QPushButton

from cfauto.ui.tema.qss import ARQUIVO_SETA_BAIXO, gerar_qss
from cfauto.ui.tema.tokens import CLARO


def test_qss_sem_placeholder_pendente():
    assert "$" not in gerar_qss(CLARO)


def test_qss_cobre_papeis_e_objetos_nomeados():
    qss = gerar_qss(CLARO)
    for trecho in (
        'QPushButton[papel="primario"]',
        'QPushButton[papel="perigo"]',
        "QPushButton:default",
        'QLabel[papel="titulo"]',
        'QLabel[papel="erro"]',
        'QLabel[papel="aviso"]',
        'QLabel[papel="sucesso"]',
        "QToolBar#faixa",
        "QFrame#lateral",
        "QListWidget#navegacao",
        "QTabBar::tab:selected",
        "QHeaderView::section",
        "QMessageBox",
        "QScrollBar",
        "QToolTip",
        "QGroupBox",
    ):
        assert trecho in qss, trecho


def test_qss_usa_os_valores_dos_tokens():
    qss = gerar_qss(CLARO)
    for valor in (
        CLARO.indigo,
        CLARO.indigo_escuro,
        CLARO.preto,
        CLARO.erro,
        CLARO.aviso,
        CLARO.sucesso,
        CLARO.perigo,
        CLARO.aviso_sobre_marca,
        CLARO.zebra,
        CLARO.sobre_marca_hover,
    ):
        assert valor in qss, valor


def test_seta_do_combo_existe_e_carrega():
    imagem = QImage(str(ARQUIVO_SETA_BAIXO))
    assert not imagem.isNull()
    assert (imagem.width(), imagem.height()) == (12, 12)


def test_qss_aponta_para_a_seta_informada():
    assert ARQUIVO_SETA_BAIXO.as_posix() in gerar_qss(CLARO)
    assert "C:/outra/seta.png" in gerar_qss(CLARO, seta_baixo=Path("C:/outra/seta.png"))


def test_qss_nao_gera_erro_de_parse(tema_isolado):
    mensagens: list[str] = []
    anterior = qInstallMessageHandler(lambda tipo, contexto, texto: mensagens.append(texto))
    try:
        # Sanidade: o handler tem que enxergar uma folha inválida, senão o teste seria vazio.
        # O Qt só faz o parse da folha da aplicação ao polir o primeiro widget.
        tema_isolado.setStyleSheet("}{ isto nao e qss")
        QPushButton("x").ensurePolished()
        invalida = [m for m in mensagens if "parse" in m.lower()]
        mensagens.clear()
        tema_isolado.setStyleSheet(gerar_qss(CLARO))
        QPushButton("x").ensurePolished()
    finally:
        qInstallMessageHandler(anterior)
    assert invalida, "o handler não capturou o erro de uma folha inválida"
    assert not [m for m in mensagens if "parse" in m.lower()]
