import logging

from cfauto.core.logs import configurar_logs


def test_configurar_logs_idempotente(tmp_path):
    configurar_logs(tmp_path)
    configurar_logs(tmp_path)
    logger = logging.getLogger("cfauto")
    arquivos = [h for h in logger.handlers if getattr(h, "baseFilename", None)]
    assert len(arquivos) == 1
    logging.getLogger("cfauto.teste").info("olá")
    for h in logger.handlers:
        h.flush()
    assert "olá" in (tmp_path / "cfauto.log").read_text(encoding="utf-8")
