import logging
import os
import subprocess
import sys

import pytest

from cfauto.ui import app
from cfauto.ui.app import main, tratar_excecao_nao_tratada


def test_verificar_instalacao(monkeypatch, tmp_path):
    monkeypatch.setenv("CFAUTO_HOME", str(tmp_path))
    assert main(["--verificar-instalacao"]) == 0
    assert (tmp_path / "cfauto.db").exists()
    assert (tmp_path / "logs" / "cfauto.log").exists()


def test_tratar_excecao_nao_tratada_loga_critical(monkeypatch, caplog):
    chamadas = []
    monkeypatch.setattr(app, "mostrar_erro", lambda pai, erro: chamadas.append((pai, erro)))
    try:
        raise ValueError("falha de teste")
    except ValueError:
        tipo, valor, tb = sys.exc_info()
    with caplog.at_level(logging.CRITICAL, logger="cfauto.ui"):
        tratar_excecao_nao_tratada(tipo, valor, tb)
    registros = [r for r in caplog.records if r.name == "cfauto.ui"]
    assert any(r.levelno == logging.CRITICAL for r in registros)
    assert registros[0].exc_info == (tipo, valor, tb)


def test_tratar_excecao_nao_tratada_delega_keyboard_interrupt(monkeypatch):
    chamado = []
    monkeypatch.setattr(sys, "__excepthook__", lambda t, v, tb: chamado.append((t, v, tb)))
    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        tipo, valor, tb = sys.exc_info()
    tratar_excecao_nao_tratada(tipo, valor, tb)
    assert chamado == [(tipo, valor, tb)]


def test_inatividade_padrao_e_5_minutos():
    assert app.MINUTOS_INATIVIDADE_PADRAO == 5


_SCRIPT_APARENCIA = """
import sys
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from cfauto.ui.app import configurar_aparencia
qapp = QApplication(sys.argv)
configurar_aparencia(qapp)
print(qapp.palette().color(QPalette.ColorRole.WindowText).lightness())
"""


@pytest.mark.skipif(sys.platform != "win32", reason="esquema de cor do plugin windows")
def test_aparencia_forca_texto_escuro_mesmo_no_modo_escuro():
    # O plugin offscreen dos testes ignora esquema de cor; roda no plugin real do Windows.
    env = {**os.environ, "QT_QPA_PLATFORM": "windows"}
    saida = subprocess.run(
        [sys.executable, "-c", _SCRIPT_APARENCIA],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert int(saida.stdout.strip().splitlines()[-1]) < 128
