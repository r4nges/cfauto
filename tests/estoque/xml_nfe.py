"""Gera XML de NF-e 4.00 sintético para os testes (chave com DV válido)."""

from dataclasses import dataclass
from decimal import Decimal
from xml.sax.saxutils import escape

from cfauto.estoque.nfe import calcular_dv

CNPJ_FORNECEDOR = "12345678000195"
CNPJ_LOJA = "98765432000110"


@dataclass(frozen=True)
class ItemXml:
    codigo: str
    descricao: str
    qtd: str
    valor_produto: str
    ean: str = "SEM GTIN"
    ean_trib: str | None = None  # None = igual ao ean
    unidade: str = "UN"
    unidade_trib: str | None = None  # None = igual à unidade
    qtd_trib: str | None = None  # None = igual à qtd
    desconto: str | None = None
    frete: str | None = None
    ipi: str | None = None
    icms_st: str | None = None


def chave_teste(numero: int, cnpj: str = CNPJ_FORNECEDOR) -> str:
    base = f"312609{cnpj}55001{numero:09d}112345678"
    return base + str(calcular_dv(base))


def _tag(nome: str, valor: str | None) -> str:
    return "" if valor is None else f"<{nome}>{escape(valor)}</{nome}>"


def _det(numero: int, item: ItemXml) -> str:
    qtd = Decimal(item.qtd)
    valor_unit = Decimal(0) if qtd == 0 else Decimal(item.valor_produto) / qtd
    prod = (
        _tag("cProd", item.codigo)
        + _tag("cEAN", item.ean)
        + _tag("xProd", item.descricao)
        + _tag("uCom", item.unidade)
        + _tag("qCom", item.qtd)
        + _tag("vUnCom", f"{valor_unit:.10f}")
        + _tag("vProd", item.valor_produto)
        + _tag("cEANTrib", item.ean if item.ean_trib is None else item.ean_trib)
        + _tag("uTrib", item.unidade if item.unidade_trib is None else item.unidade_trib)
        + _tag("qTrib", item.qtd if item.qtd_trib is None else item.qtd_trib)
        + _tag("vFrete", item.frete)
        + _tag("vDesc", item.desconto)
        + "<indTot>1</indTot>"
    )
    if item.icms_st is None:
        icms = "<ICMSSN102><CSOSN>102</CSOSN></ICMSSN102>"
    else:
        icms = f"<ICMS10><CST>10</CST>{_tag('vICMSST', item.icms_st)}</ICMS10>"
    ipi = "" if item.ipi is None else f"<IPI><IPITrib>{_tag('vIPI', item.ipi)}</IPITrib></IPI>"
    imposto = f"<imposto><ICMS>{icms}</ICMS>{ipi}</imposto>"
    return f'<det nItem="{numero}"><prod>{prod}</prod>{imposto}</det>'


def _custo(item: ItemXml) -> Decimal:
    partes = (item.frete, item.ipi, item.icms_st)
    acrescimos = sum((Decimal(p) for p in partes if p is not None), Decimal(0))
    return Decimal(item.valor_produto) - Decimal(item.desconto or "0") + acrescimos


def montar_nfe(
    numero: int,
    itens: list[ItemXml],
    *,
    cnpj_emitente: str = CNPJ_FORNECEDOR,
    nome_emitente: str = "Distribuidora Boa Vista Ltda",
    cnpj_destinatario: str | None = CNPJ_LOJA,
    com_protocolo: bool = True,
) -> bytes:
    chave = chave_teste(numero, cnpj_emitente)
    total = sum((_custo(item) for item in itens), Decimal(0))
    destinatario = (
        ""
        if cnpj_destinatario is None
        else f"<dest>{_tag('CNPJ', cnpj_destinatario)}<xNome>Loja</xNome></dest>"
    )
    dets = "".join(_det(n, item) for n, item in enumerate(itens, start=1))
    nfe = (
        '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        f'<infNFe Id="NFe{chave}" versao="4.00">'
        f"<ide><cUF>31</cUF><mod>55</mod><serie>1</serie><nNF>{numero}</nNF>"
        "<dhEmi>2026-09-20T10:15:00-03:00</dhEmi></ide>"
        f"<emit>{_tag('CNPJ', cnpj_emitente)}{_tag('xNome', nome_emitente)}</emit>"
        f"{destinatario}{dets}"
        f"<total><ICMSTot><vNF>{total:.2f}</vNF></ICMSTot></total>"
        "</infNFe></NFe>"
    )
    if com_protocolo:
        corpo = (
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
            f"{nfe}<protNFe><infProt><chNFe>{chave}</chNFe><cStat>100</cStat></infProt>"
            "</protNFe></nfeProc>"
        )
    else:
        corpo = nfe
    return ('<?xml version="1.0" encoding="UTF-8"?>' + corpo).encode("utf-8")
