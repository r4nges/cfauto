"""Leitura do XML de NF-e/NFC-e (layout 4.00). Puro: não acessa o banco."""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as XmlSeguro
from defusedxml.common import DefusedXmlException

from cfauto.core.dates import para_data
from cfauto.core.errors import DataInvalida, XmlInvalido
from cfauto.core.money import arredondar
from cfauto.core.texto import normalizar_texto

_NS = {"n": "http://www.portalfiscal.inf.br/nfe"}
_TAG_NFE_PROC = "{http://www.portalfiscal.inf.br/nfe}nfeProc"
_TAG_NFE = "{http://www.portalfiscal.inf.br/nfe}NFe"
_PESOS_DV = (2, 3, 4, 5, 6, 7, 8, 9)
_TAMANHO_MAXIMO_EAN = 14


@dataclass(frozen=True)
class ItemNotaLido:
    n_item: int
    codigo: str
    ean: str | None
    ean_trib: str | None
    descricao: str
    unidade: str
    qtd: Decimal
    valor_unit: Decimal
    unidade_trib: str
    qtd_trib: Decimal
    valor_produto: Decimal
    desconto: Decimal
    frete: Decimal
    seguro: Decimal
    outros: Decimal
    ipi: Decimal
    icms_st: Decimal  # vICMSST + vFCPST

    @property
    def custo_total(self) -> Decimal:
        """Custo efetivo do item: o que a loja realmente pagou (decisão D2)."""
        return arredondar(
            self.valor_produto
            - self.desconto
            + self.frete
            + self.seguro
            + self.outros
            + self.ipi
            + self.icms_st
        )


@dataclass(frozen=True)
class NotaFiscalLida:
    chave: str
    numero: int
    serie: int
    modelo: int
    data_emissao: date
    emitente_documento: str
    emitente_nome: str
    destinatario_documento: str | None
    valor_total: Decimal
    itens: tuple[ItemNotaLido, ...]


def calcular_dv(base: str) -> int:
    """Dígito verificador da chave (módulo 11, pesos 2..9 da direita para a esquerda)."""
    soma = sum(int(d) * _PESOS_DV[i % 8] for i, d in enumerate(reversed(base)))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def chave_valida(chave: str) -> bool:
    if len(chave) != 44 or not (chave.isascii() and chave.isdigit()):
        return False
    return calcular_dv(chave[:43]) == int(chave[43])


def ler_nfe(conteudo: bytes) -> NotaFiscalLida:
    try:
        raiz = XmlSeguro.fromstring(conteudo)
    except (XmlSeguro.ParseError, DefusedXmlException) as erro:
        raise XmlInvalido("O arquivo não é um XML válido.") from erro
    inf = _inf_nfe(raiz)
    chave = inf.get("Id", "").removeprefix("NFe")
    if not chave_valida(chave):
        raise XmlInvalido("Chave de acesso da NF-e inválida.")
    emissao = _texto(inf, "n:ide/n:dhEmi") or _obrigatorio(inf, "n:ide/n:dEmi", "dhEmi")
    try:
        data_emissao = para_data(emissao)
    except DataInvalida as erro:
        raise XmlInvalido(f"Data de emissão inválida: {emissao!r}.") from erro
    itens = tuple(_item(det) for det in inf.findall("n:det", _NS))
    if not itens:
        raise XmlInvalido("NF-e sem itens.")
    return NotaFiscalLida(
        chave=chave,
        numero=_inteiro(inf, "n:ide/n:nNF", "nNF"),
        serie=_inteiro(inf, "n:ide/n:serie", "serie"),
        modelo=_inteiro(inf, "n:ide/n:mod", "mod"),
        data_emissao=data_emissao,
        emitente_documento=_texto(inf, "n:emit/n:CNPJ")
        or _obrigatorio(inf, "n:emit/n:CPF", "CNPJ do emitente"),
        emitente_nome=_obrigatorio(inf, "n:emit/n:xNome", "nome do emitente"),
        destinatario_documento=_texto(inf, "n:dest/n:CNPJ") or _texto(inf, "n:dest/n:CPF"),
        valor_total=_decimal(inf, "n:total/n:ICMSTot/n:vNF", "vNF", obrigatorio=True),
        itens=itens,
    )


def _inf_nfe(raiz: Element) -> Element:
    if raiz.tag == _TAG_NFE_PROC:
        nfe = raiz.find("n:NFe", _NS)
    elif raiz.tag == _TAG_NFE:
        nfe = raiz
    else:
        nfe = None
    inf = None if nfe is None else nfe.find("n:infNFe", _NS)
    if inf is None:
        raise XmlInvalido("O arquivo não é o XML de uma NF-e (esperado nfeProc ou NFe).")
    return inf


def _item(det: Element) -> ItemNotaLido:
    n_item_texto = det.get("nItem", "")
    if not (n_item_texto.isascii() and n_item_texto.isdigit()):
        raise XmlInvalido("Item da NF-e sem número (nItem).")
    n_item = int(n_item_texto)
    prod = det.find("n:prod", _NS)
    if prod is None:
        raise XmlInvalido(f"Item {n_item} da NF-e sem dados do produto.")
    qtd = _decimal(prod, "n:qCom", "qCom", obrigatorio=True)
    if qtd <= 0:
        raise XmlInvalido(f"Item {n_item}: quantidade inválida ({qtd}).")
    unidade = _obrigatorio(prod, "n:uCom", "uCom")
    return ItemNotaLido(
        n_item=n_item,
        codigo=_obrigatorio(prod, "n:cProd", "cProd"),
        ean=_ean(_texto(prod, "n:cEAN")),
        ean_trib=_ean(_texto(prod, "n:cEANTrib")),
        descricao=_obrigatorio(prod, "n:xProd", "xProd"),
        unidade=unidade,
        qtd=qtd,
        valor_unit=_decimal(prod, "n:vUnCom", "vUnCom"),
        unidade_trib=_texto(prod, "n:uTrib") or unidade,
        qtd_trib=_decimal(prod, "n:qTrib", "qTrib") or qtd,
        valor_produto=_decimal(prod, "n:vProd", "vProd", obrigatorio=True),
        desconto=_decimal(prod, "n:vDesc", "vDesc"),
        frete=_decimal(prod, "n:vFrete", "vFrete"),
        seguro=_decimal(prod, "n:vSeg", "vSeg"),
        outros=_decimal(prod, "n:vOutro", "vOutro"),
        ipi=_decimal(det, "n:imposto/n:IPI/n:IPITrib/n:vIPI", "vIPI"),
        icms_st=_decimal(det, "n:imposto/n:ICMS/*/n:vICMSST", "vICMSST")
        + _decimal(det, "n:imposto/n:ICMS/*/n:vFCPST", "vFCPST"),
    )


def _texto(pai: Element, caminho: str) -> str | None:
    elemento = pai.find(caminho, _NS)
    if elemento is None or elemento.text is None:
        return None
    return elemento.text.strip() or None


def _obrigatorio(pai: Element, caminho: str, rotulo: str) -> str:
    valor = _texto(pai, caminho)
    if valor is None:
        raise XmlInvalido(f"NF-e sem o campo obrigatório {rotulo}.")
    return valor


def _decimal(pai: Element, caminho: str, rotulo: str, *, obrigatorio: bool = False) -> Decimal:
    texto = _obrigatorio(pai, caminho, rotulo) if obrigatorio else _texto(pai, caminho)
    if texto is None:
        return Decimal(0)
    try:
        valor = Decimal(texto)  # o XML usa ponto decimal: nunca para_decimal ("1.000" é 1)
    except InvalidOperation as erro:
        raise XmlInvalido(f"Valor inválido em {rotulo}: {texto!r}.") from erro
    if not valor.is_finite():
        raise XmlInvalido(f"Valor inválido em {rotulo}: {texto!r}.")
    return valor


def _inteiro(pai: Element, caminho: str, rotulo: str) -> int:
    texto = _obrigatorio(pai, caminho, rotulo)
    if not (texto.isascii() and texto.isdigit()):
        raise XmlInvalido(f"Valor inválido em {rotulo}: {texto!r}.")
    return int(texto)


def _ean(texto: str | None) -> str | None:
    """'SEM GTIN', vazio ou não numérico → None."""
    if texto is None or not (texto.isascii() and texto.isdigit()):
        return None
    return texto if len(texto) <= _TAMANHO_MAXIMO_EAN else None


# Port de extrairFator (01-ESTOQUE.gs:518-530), aplicado sobre o texto normalizado.
_RE_CONTAGENS = re.compile(
    r"(?:c/|cx\b|caixa\b)?\s*\d+\s*(?:capsulas|capsula|caps|cap|comprimidos|comprimido|comp"
    r"|drageas|dragea|softgel|gomas|goma|pastilhas|pastilha|saches|sache)\b"
)
_RE_MEDIDAS = re.compile(r"\b\d+\s*(?:kg|g|mg|mcg|l|ml)\b")
_RE_MULTIPLO = re.compile(r"(\d+)\s*x\s*\d+")
_RE_EMBALAGEM = re.compile(r"(?:c/|cx|caixa|fardo|pack|display)\s*(\d+)")
_RE_UNIDADES = re.compile(r"(\d+)\s*unidades?\b")


def fator_pela_descricao(descricao: str) -> int:
    """Unidades por embalagem lidas do nome ("C/12", "12X350ML", "PACK 6"); senão 1."""
    texto = _RE_MEDIDAS.sub("", _RE_CONTAGENS.sub("", normalizar_texto(descricao)))
    for regex in (_RE_MULTIPLO, _RE_EMBALAGEM, _RE_UNIDADES):
        achado = regex.search(texto)
        if achado is not None and int(achado.group(1)) > 0:
            return int(achado.group(1))
    return 1


def sugerir_fator(
    descricao: str, unidade: str, qtd: Decimal, unidade_trib: str, qtd_trib: Decimal
) -> Decimal:
    """Unidades de estoque por unidade comercial da nota. Só sugestão: o usuário confere."""
    if unidade_trib.strip().upper() != unidade.strip().upper() and qtd > 0:
        razao = qtd_trib / qtd
        if razao > 1 and razao == razao.to_integral_value():
            return razao.to_integral_value()
    return Decimal(fator_pela_descricao(descricao))
