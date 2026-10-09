from pathlib import Path

import cfauto.ui

RAIZ_UI = Path(cfauto.ui.__file__).parent


def test_tabelas_montadas_a_mao_ligam_a_zebra():
    sem_zebra = []
    for arquivo in sorted(RAIZ_UI.rglob("*.py")):
        if arquivo.name == "comum.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "QTableWidget(" in texto and "setAlternatingRowColors(True)" not in texto:
            sem_zebra.append(arquivo.relative_to(RAIZ_UI).as_posix())
    assert not sem_zebra, f"tabelas sem zebra: {sem_zebra}"
