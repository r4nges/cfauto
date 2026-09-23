import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configurar_logs(pasta: Path, nivel: int = logging.INFO) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("cfauto")
    logger.setLevel(nivel)
    arquivo = str(pasta / "cfauto.log")
    for handler in list(logger.handlers):
        if getattr(handler, "baseFilename", None) is not None:
            if handler.baseFilename == arquivo:  # type: ignore[attr-defined]
                return
            logger.removeHandler(handler)
            handler.close()
    handler = RotatingFileHandler(arquivo, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
