"""Tokens do tema. É o único arquivo de cfauto/ui com literais de cor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tokens:
    indigo: str
    indigo_escuro: str
    preto: str
    sobre_marca: str
    sobre_marca_hover: str
    fundo: str
    superficie: str
    linha: str
    linha_campo: str
    cabecalho_tabela: str
    zebra: str
    selecao: str
    texto: str
    texto_secundario: str
    sucesso: str
    sucesso_fundo: str
    aviso: str
    aviso_fundo: str
    perigo: str
    perigo_fundo: str
    erro: str
    aviso_sobre_marca: str
    raio_controle: int
    raio_painel: int
    fonte_familia: str
    fonte_pt: int
    fonte_navegacao_pt: int


CLARO = Tokens(
    indigo="#3433cc",
    indigo_escuro="#14124f",
    preto="#000000",
    sobre_marca="#ffffff",
    sobre_marca_hover="rgba(255, 255, 255, 40)",
    fundo="#f6f7fb",
    superficie="#ffffff",
    linha="#dde0ee",
    linha_campo="#c4c8dc",
    cabecalho_tabela="#e9eaf8",
    zebra="#f9faff",
    selecao="#ecebff",
    texto="#1f2233",
    texto_secundario="#5b5f7a",
    sucesso="#1d6b34",
    sucesso_fundo="#dff3e4",
    aviso="#8a5a00",
    aviso_fundo="#fdf0d3",
    perigo="#a3231a",
    perigo_fundo="#fbdedb",
    erro="#b3261e",
    aviso_sobre_marca="#ffd27a",
    raio_controle=4,
    raio_painel=6,
    fonte_familia="Segoe UI",
    fonte_pt=10,
    fonte_navegacao_pt=12,
)
