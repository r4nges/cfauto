from cfauto.ui.app import main


def test_verificar_instalacao(monkeypatch, tmp_path):
    monkeypatch.setenv("CFAUTO_HOME", str(tmp_path))
    assert main(["--verificar-instalacao"]) == 0
    assert (tmp_path / "cfauto.db").exists()
    assert (tmp_path / "logs" / "cfauto.log").exists()
