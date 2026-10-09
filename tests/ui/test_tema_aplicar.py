import logging

from PySide6.QtGui import QColor, QPalette

from cfauto.ui.tema import CLARO, aplicar, aplicar_tema


def _partir_de_estilo_nao_fusion(qapp) -> None:
    """O estilo padrão do offscreen já é Fusion: sem este pré-ajuste, afirmar "fusion" depois
    de `aplicar_tema` passaria mesmo sem o passo do estilo. A fixture restaura o estilo."""
    qapp.setStyle("Windows")
    assert qapp.style().objectName().lower() == "windows"


def _estilo_base(qapp) -> str:
    """Com folha de estilo, `style()` é o QStyleSheetStyle (objectName vazio); sem a folha,
    volta o estilo base. Chamar por último: limpa a folha da aplicação."""
    qapp.setStyleSheet("")
    return qapp.style().objectName().lower()


def test_aplica_fusion_paleta_fonte_e_folha(tema_isolado):
    _partir_de_estilo_nao_fusion(tema_isolado)
    aplicar_tema(tema_isolado)
    assert tema_isolado.styleSheet()
    paleta = tema_isolado.palette()
    assert paleta.color(QPalette.ColorRole.WindowText) == QColor(CLARO.texto)
    assert paleta.color(QPalette.ColorRole.Window) == QColor(CLARO.superficie)
    assert paleta.color(QPalette.ColorRole.Highlight) == QColor(CLARO.indigo)
    assert tema_isolado.font().pointSize() == CLARO.fonte_pt
    assert _estilo_base(tema_isolado) == "fusion"


def test_traducao_pt_br_instalada(tema_isolado):
    aplicar_tema(tema_isolado)
    assert tema_isolado.translate("QPlatformTheme", "Cancel") == "Cancelar"


def test_arquivo_de_traducao_vai_junto_no_repo():
    assert (aplicar.RECURSOS / "qtbase_pt_BR.qm").is_file()


def test_sem_arquivo_de_traducao_nao_levanta_e_loga(tema_isolado, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(aplicar, "_pastas_traducao", lambda: [tmp_path])
    _partir_de_estilo_nao_fusion(tema_isolado)
    with caplog.at_level(logging.WARNING, logger="cfauto.ui"):
        aplicar_tema(tema_isolado)
    assert any("qtbase_pt_BR.qm" in r.getMessage() for r in caplog.records)
    assert _estilo_base(tema_isolado) == "fusion"


def test_sem_seta_do_combo_loga_e_aplica_a_folha_mesmo_assim(
    tema_isolado, monkeypatch, tmp_path, caplog
):
    monkeypatch.setattr(aplicar, "ARQUIVO_SETA_BAIXO", tmp_path / "seta-baixo.png")
    _partir_de_estilo_nao_fusion(tema_isolado)
    with caplog.at_level(logging.WARNING, logger="cfauto.ui"):
        aplicar_tema(tema_isolado)
    assert any("seta-baixo.png" in r.getMessage() for r in caplog.records)
    assert tema_isolado.styleSheet()
    assert _estilo_base(tema_isolado) == "fusion"


def test_passo_com_falha_nao_interrompe_os_seguintes(tema_isolado, monkeypatch, caplog):
    def quebrar(*args, **kwargs):
        raise RuntimeError("qss quebrado")

    monkeypatch.setattr(aplicar, "gerar_qss", quebrar)
    with caplog.at_level(logging.ERROR, logger="cfauto.ui"):
        aplicar_tema(tema_isolado)
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert tema_isolado.translate("QPlatformTheme", "Cancel") == "Cancelar"


def test_aplicar_duas_vezes_nao_empilha_tradutores(tema_isolado):
    aplicar_tema(tema_isolado)
    primeiro = aplicar._tradutor
    aplicar_tema(tema_isolado)
    assert aplicar._tradutor is not primeiro
    assert tema_isolado.translate("QPlatformTheme", "Cancel") == "Cancelar"
    tema_isolado.removeTranslator(aplicar._tradutor)
    aplicar._tradutor = None
    assert tema_isolado.translate("QPlatformTheme", "Cancel") == "Cancel"
