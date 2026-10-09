import dataclasses

import pytest

from cfauto.ui.tema import CLARO, Tokens


def _luminancia(cor: str) -> float:
    r, g, b = (int(cor[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def canal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _contraste(a: str, b: str) -> float:
    claro, escuro = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


PARES = [
    ("texto", "fundo"),
    ("texto", "superficie"),
    ("texto", "zebra"),
    ("texto", "selecao"),
    ("texto", "cabecalho_tabela"),
    ("texto_secundario", "fundo"),
    ("texto_secundario", "superficie"),
    ("sucesso", "sucesso_fundo"),
    ("sucesso", "superficie"),
    ("aviso", "aviso_fundo"),
    ("aviso", "superficie"),
    ("perigo", "perigo_fundo"),
    ("perigo", "superficie"),
    ("erro", "superficie"),
    ("aviso_sobre_marca", "indigo_escuro"),
    ("aviso_sobre_marca", "indigo"),
    ("sobre_marca", "indigo"),
    ("sobre_marca", "indigo_escuro"),
    ("sobre_marca", "preto"),
    ("indigo", "selecao"),
    ("indigo", "superficie"),
    ("indigo", "fundo"),
]


@pytest.mark.parametrize(("texto", "fundo"), PARES)
def test_contraste_minimo_wcag(texto, fundo):
    razao = _contraste(getattr(CLARO, texto), getattr(CLARO, fundo))
    assert razao >= 4.5, f"{texto} sobre {fundo}: {razao:.2f}:1"


def test_tokens_sao_imutaveis():
    with pytest.raises(dataclasses.FrozenInstanceError):
        CLARO.indigo = "#000000"  # type: ignore[misc]


def test_cores_hex_sao_rrggbb():
    for campo in dataclasses.fields(Tokens):
        valor = getattr(CLARO, campo.name)
        if isinstance(valor, str) and valor.startswith("#"):
            assert len(valor) == 7, campo.name
            int(valor[1:], 16)
