import re
from pathlib import Path

import cfauto.ui

RAIZ_UI = Path(cfauto.ui.__file__).parent

_COR_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_COR_FUNCAO = re.compile(r"\brgba?\(")


def _arquivos_ui_fora_dos_tokens():
    tokens = RAIZ_UI / "tema" / "tokens.py"
    return [a for a in sorted(RAIZ_UI.rglob("*.py")) if a != tokens]


def test_tabelas_montadas_a_mao_ligam_a_zebra():
    sem_zebra = []
    for arquivo in sorted(RAIZ_UI.rglob("*.py")):
        if arquivo.name == "comum.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "QTableWidget(" in texto and "setAlternatingRowColors(True)" not in texto:
            sem_zebra.append(arquivo.relative_to(RAIZ_UI).as_posix())
    assert not sem_zebra, f"tabelas sem zebra: {sem_zebra}"


def test_nenhum_literal_de_cor_fora_dos_tokens():
    achados = []
    for arquivo in _arquivos_ui_fora_dos_tokens():
        texto = arquivo.read_text(encoding="utf-8")
        if _COR_HEX.search(texto) or _COR_FUNCAO.search(texto):
            achados.append(arquivo.relative_to(RAIZ_UI).as_posix())
    assert not achados, f"literais de cor fora de tema/tokens.py: {achados}"


def test_setstylesheet_so_no_aplicar_tema():
    permitido = RAIZ_UI / "tema" / "aplicar.py"
    achados = [
        a.relative_to(RAIZ_UI).as_posix()
        for a in _arquivos_ui_fora_dos_tokens()
        if a != permitido and "setStyleSheet(" in a.read_text(encoding="utf-8")
    ]
    assert not achados, f"setStyleSheet fora do tema: {achados}"
