"""Extrato do cliente em HTML para impressão via QTextDocument (função pura)."""

from datetime import datetime
from html import escape

from cfauto.clientes.models import TITULOS_MOTIVO_LANCAMENTO, TipoLancamento
from cfauto.clientes.schemas import Extrato, LinhaLancamento
from cfauto.clientes.validacao import formatar_celular, formatar_cpf, formatar_saldo
from cfauto.core.money import formatar_brl


def descrever_lancamento(linha: LinhaLancamento) -> str:
    titulo = TITULOS_MOTIVO_LANCAMENTO[linha.motivo]
    return f"{titulo} — {linha.observacao}" if linha.observacao else titulo


def _linha_html(linha: LinhaLancamento) -> str:
    debito = formatar_brl(linha.valor) if linha.tipo == TipoLancamento.DEBITO else ""
    credito = formatar_brl(linha.valor) if linha.tipo == TipoLancamento.CREDITO else ""
    return (
        "<tr>"
        f"<td>{linha.data_hora:%d/%m/%Y %H:%M}</td>"
        f"<td>{escape(descrever_lancamento(linha))}</td>"
        f'<td align="right">{debito}</td>'
        f'<td align="right">{credito}</td>'
        f'<td align="right">{escape(formatar_saldo(linha.saldo_apos))}</td>'
        "</tr>"
    )


def gerar_html_extrato(extrato: Extrato, loja: str, emitido_em: datetime) -> str:
    cliente = extrato.cliente
    cpf = f" · CPF {formatar_cpf(cliente.cpf)}" if cliente.cpf else ""
    if extrato.linhas:
        corpo = "".join(_linha_html(linha) for linha in extrato.linhas)
    else:
        corpo = '<tr><td colspan="5">Nenhum lançamento no período.</td></tr>'
    return (
        "<html><body>"
        f"<h2>{escape(loja)}</h2>"
        "<h3>Extrato do cliente</h3>"
        f"<p>{escape(cliente.codigo)} — {escape(cliente.nome)}{cpf}"
        f" · Celular {formatar_celular(cliente.celular)}</p>"
        f"<p>Período: {extrato.inicio:%d/%m/%Y} a {extrato.fim:%d/%m/%Y}</p>"
        f"<p>Saldo anterior: {escape(formatar_saldo(extrato.saldo_anterior))}</p>"
        '<table border="1" cellspacing="0" cellpadding="4" width="100%">'
        "<tr><th>Data</th><th>Descrição</th><th>Débito</th><th>Crédito</th><th>Saldo</th></tr>"
        f"{corpo}</table>"
        f"<p><b>Saldo final: {escape(formatar_saldo(extrato.saldo_final))}</b></p>"
        f"<p>Emitido em {emitido_em:%d/%m/%Y %H:%M}</p>"
        "</body></html>"
    )
