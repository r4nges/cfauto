from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWizard

from cfauto.ui.assistente import AssistentePrimeiraExecucao


def test_assistente_tem_tamanho_fixo_estilo_moderno_e_marca_lateral(qtbot, fabrica):
    assistente = AssistentePrimeiraExecucao(fabrica)
    qtbot.addWidget(assistente)
    assert assistente.wizardStyle() == QWizard.WizardStyle.ModernStyle
    assert assistente.minimumSize() == assistente.maximumSize() == QSize(640, 440)
    marca = assistente.pixmap(QWizard.WizardPixmap.WatermarkPixmap)
    assert not marca.isNull()
    assert marca.width() == 210


def test_assistente_continua_com_as_tres_paginas(qtbot, fabrica):
    assistente = AssistentePrimeiraExecucao(fabrica)
    qtbot.addWidget(assistente)
    assert len(assistente.pageIds()) == 3
    assert assistente.windowTitle() == "CFAUTO — Primeira execução"
