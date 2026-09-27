import importlib.util
from datetime import date
from pathlib import Path

import pytest

from cfauto.licenca.formato import carregar_publica_hex, verificar_assinatura

_spec = importlib.util.spec_from_file_location(
    "gerar_licenca", Path(__file__).parents[2] / "tools" / "gerar_licenca.py"
)
gerar_licenca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gerar_licenca)


def test_gerar_par_e_emitir(tmp_path):
    privada = tmp_path / "privada.pem"
    hex_publica = gerar_licenca.gerar_par(privada)
    assert privada.exists()
    chave = gerar_licenca.emitir_chave(privada, "Loja X", date(2027, 1, 1), "abcd")
    payload = verificar_assinatura(chave, carregar_publica_hex(hex_publica))
    assert payload.cliente == "Loja X"
    assert payload.expira == date(2027, 1, 1)
    assert payload.maquina == "abcd"


def test_gerar_par_nao_sobrescreve(tmp_path):
    privada = tmp_path / "privada.pem"
    gerar_licenca.gerar_par(privada)
    with pytest.raises(FileExistsError):
        gerar_licenca.gerar_par(privada)
