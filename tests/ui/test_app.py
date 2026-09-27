import logging
import sys

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
