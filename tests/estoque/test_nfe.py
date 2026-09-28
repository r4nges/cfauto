from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cfauto.core.errors import XmlInvalido
from cfauto.estoque.nfe import (
    calcular_dv,
    chave_valida,
    fator_pela_descricao,
    ler_nfe,
    sugerir_fator,
)
from tests.estoque.xml_nfe import ItemXml, chave_teste, montar_nfe

FIXTURES = Path(__file__).parent / "fixtures"
CHAVE_COMPLETA = "31260912345678000195550010000012341123456789"


def _completa() -> bytes:
    return (FIXTURES / "nfe_completa.xml").read_bytes()


def test_dv_confere_com_o_exemplo_do_manual_da_nfe():
    assert calcular_dv("3508059999909091027055001000000001518005127") == 3
    assert chave_valida("35080599999090910270550010000000015180051273")
    assert not chave_valida("35080599999090910270550010000000015180051274")
    assert not chave_valida("123")


def test_le_o_cabecalho_da_nota_completa():
    nota = ler_nfe(_completa())
    assert nota.chave == CHAVE_COMPLETA
    assert (nota.numero, nota.serie, nota.modelo) == (1234, 1, 55)
    assert nota.data_emissao == date(2026, 9, 20)
    assert nota.emitente_documento == "12345678000195"
    assert nota.emitente_nome == "Distribuidora Boa Vista Ltda"
    assert nota.destinatario_documento == "98765432000110"
    assert nota.valor_total == Decimal("147.60")
    assert [i.n_item for i in nota.itens] == [1, 2, 3]


def test_le_os_itens_e_o_custo_efetivo():
    um, dois, tres = ler_nfe(_completa()).itens
    assert (um.codigo, um.ean, um.qtd, um.custo_total) == (
        "A-100",
        "7891000100103",
        Decimal("10"),
        Decimal("75.00"),
    )
    assert (dois.ean, dois.ean_trib) == (None, None)
    assert (dois.unidade, dois.unidade_trib, dois.qtd_trib) == ("CX", "UN", Decimal("200"))
    assert tres.ean_trib == "7891000300312"
    assert (tres.desconto, tres.frete, tres.seguro, tres.outros) == (
        Decimal("1.50"),
        Decimal("3.00"),
        Decimal("0.50"),
        Decimal("0.40"),
    )
    assert (tres.ipi, tres.icms_st) == (Decimal("1.80"), Decimal("2.40"))
    assert tres.custo_total == Decimal("42.60")


def test_nfe_sem_protocolo_e_aceita():
    nota = ler_nfe(montar_nfe(10, [ItemXml("X-1", "Produto", "1", "5.00")], com_protocolo=False))
    assert nota.chave == chave_teste(10)
    assert nota.itens[0].custo_total == Decimal("5.00")


def test_quantidade_usa_ponto_decimal_do_xml():
    xml = montar_nfe(
        11,
        [
            ItemXml("X-1", "Queijo", "1.000", "40.00", unidade="KG"),
            ItemXml("X-2", "Presunto", "2.5000", "87.50", unidade="KG"),
        ],
    )
    um, dois = ler_nfe(xml).itens
    assert um.qtd == Decimal("1")
    assert dois.qtd == Decimal("2.5")


def test_sem_destinatario():
    xml = montar_nfe(12, [ItemXml("X-1", "Produto", "1", "5.00")], cnpj_destinatario=None)
    assert ler_nfe(xml).destinatario_documento is None


@pytest.mark.parametrize(
    ("conteudo", "mensagem"),
    [
        (b"<nfeProc><NFe>", "XML válido"),
        (b"", "XML válido"),
        (
            b'<procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe"><evento/></procEventoNFe>',
            "não é o XML de uma NF-e",
        ),
        (b"<html><body>oi</body></html>", "não é o XML de uma NF-e"),
    ],
)
def test_arquivos_que_nao_sao_nfe(conteudo, mensagem):
    with pytest.raises(XmlInvalido, match=mensagem):
        ler_nfe(conteudo)


def test_chave_com_dv_errado():
    errada = CHAVE_COMPLETA[:-1] + "0"
    xml = _completa().replace(CHAVE_COMPLETA.encode(), errada.encode())
    with pytest.raises(XmlInvalido, match="Chave"):
        ler_nfe(xml)


def test_nota_sem_itens():
    with pytest.raises(XmlInvalido, match="sem itens"):
        ler_nfe(montar_nfe(13, []))


def test_quantidade_zero_e_invalida():
    with pytest.raises(XmlInvalido, match="quantidade"):
        ler_nfe(montar_nfe(14, [ItemXml("X-1", "Brinde", "0", "0.00")]))


def test_valor_nao_numerico():
    xml = montar_nfe(15, [ItemXml("X-1", "Produto", "1", "5.00")]).replace(
        b"<vProd>5.00</vProd>", b"<vProd>cinco</vProd>"
    )
    with pytest.raises(XmlInvalido, match="vProd"):
        ler_nfe(xml)


@pytest.mark.parametrize(
    ("descricao", "esperado"),
    [
        ("AGUA MINERAL 500ML C/12", 12),
        ("CERVEJA LATA 12X350ML", 12),
        ("SABONETE PACK 6", 6),
        ("PILHA 4 UNIDADES", 4),
        ("VITAMINA C 60 CÁPSULAS", 1),
        ("Refrigerante 2L", 1),
        ("Caixa de som", 1),
    ],
)
def test_fator_pela_descricao(descricao, esperado):
    assert fator_pela_descricao(descricao) == esperado


def test_sugerir_fator():
    assert sugerir_fator("PARAFUSO", "CX", Decimal("2"), "UN", Decimal("200")) == Decimal("100")
    assert sugerir_fator("QUEIJO", "KG", Decimal("2.5"), "KG", Decimal("2.5")) == Decimal("1")
    assert sugerir_fator("AGUA C/12", "FD", Decimal("3"), "UN", Decimal("4")) == Decimal("12")
