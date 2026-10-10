import importlib.util
import struct
from pathlib import Path


def _carregar():
    caminho = Path(__file__).resolve().parents[2] / "tools" / "gerar_recursos.py"
    spec = importlib.util.spec_from_file_location("gerar_recursos", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_montar_ico_tem_cabecalho_entradas_e_dados():
    modulo = _carregar()
    ico = modulo.montar_ico([(16, b"A" * 10), (256, b"B" * 20)])
    assert struct.unpack_from("<HHH", ico) == (0, 1, 2)
    largura, altura, _, _, planos, bits, tamanho, deslocamento = struct.unpack_from(
        "<BBBBHHII", ico, 6
    )
    assert (largura, altura, planos, bits, tamanho) == (16, 16, 1, 32, 10)
    assert ico[deslocamento : deslocamento + 10] == b"A" * 10
    assert struct.unpack_from("<B", ico, 6 + 16)[0] == 0  # 256 px é gravado como 0


def test_icone_do_repo_e_um_ico_com_quatro_tamanhos():
    modulo = _carregar()
    dados = (modulo.RECURSOS / "icone.ico").read_bytes()
    assert struct.unpack_from("<HHH", dados) == (0, 1, 4)
    larguras = [struct.unpack_from("<B", dados, 6 + 16 * i)[0] for i in range(4)]
    assert larguras == [16, 32, 48, 0]
