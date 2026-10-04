from datetime import date, datetime
from decimal import Decimal

import pytest

from cfauto.clientes.extrato_html import descrever_lancamento, gerar_html_extrato
from cfauto.clientes.models import TITULOS_MOTIVO_LANCAMENTO, MotivoLancamento, TipoLancamento
from cfauto.clientes.schemas import Extrato, LinhaLancamento, ResumoCliente

CLIENTE = ResumoCliente(
    id=1,
    codigo="CLI-0001",
    nome="Ana Souza",
    celular="11987654321",
    cpf="52998224725",
    saldo_devedor=Decimal("90.50"),
    limite=Decimal("500.00"),
    disponivel=Decimal("409.50"),
    ativo=True,
)


def _linha(tipo, valor, saldo, motivo=MotivoLancamento.COMPRA_ANOTADA, observacao=""):
    return LinhaLancamento(
        id=1,
        data_hora=datetime(2026, 9, 10, 14, 5),
        tipo=tipo,
        valor=Decimal(valor),
        saldo_apos=Decimal(saldo),
        motivo=motivo,
        observacao=observacao,
        usuario="Maria",
    )


def _extrato(linhas, saldo_anterior="0", saldo_final="0"):
    return Extrato(
        cliente=CLIENTE,
        inicio=date(2026, 9, 1),
        fim=date(2026, 9, 30),
        saldo_anterior=Decimal(saldo_anterior),
        linhas=tuple(linhas),
        saldo_final=Decimal(saldo_final),
    )


def test_descrever_lancamento():
    assert descrever_lancamento(_linha(TipoLancamento.DEBITO, "1", "1")) == "Compra anotada"
    com_obs = _linha(TipoLancamento.CREDITO, "1", "0", MotivoLancamento.PAGAMENTO, "PIX")
    assert descrever_lancamento(com_obs) == "Pagamento — PIX"


@pytest.mark.parametrize("motivo", list(MotivoLancamento))
def test_todo_motivo_tem_titulo_no_extrato(motivo):
    linha = _linha(TipoLancamento.DEBITO, "10", "10", motivo=motivo)
    assert descrever_lancamento(linha) == TITULOS_MOTIVO_LANCAMENTO[motivo]


def test_html_tem_cabecalho_linhas_e_saldos():
    linhas = [
        _linha(TipoLancamento.DEBITO, "120.50", "130.50"),
        _linha(TipoLancamento.CREDITO, "40", "90.50", MotivoLancamento.PAGAMENTO),
    ]
    html = gerar_html_extrato(
        _extrato(linhas, "10", "90.50"), "Loja & Cia", datetime(2026, 9, 28, 14, 30)
    )
    for trecho in [
        "Loja &amp; Cia",
        "CLI-0001",
        "Ana Souza",
        "529.982.247-25",
        "(11) 98765-4321",
        "01/09/2026 a 30/09/2026",
        "Saldo anterior: R$ 10,00",
        "10/09/2026 14:05",
        "R$ 120,50",
        "Pagamento",
        "Saldo final: R$ 90,50",
        "Emitido em 28/09/2026 14:30",
    ]:
        assert trecho in html, trecho


def test_html_escapa_texto_do_usuario_e_mostra_credito_a_favor():
    linha = _linha(
        TipoLancamento.CREDITO, "30", "-30", MotivoLancamento.OUTRO, "<script>x</script>"
    )
    html = gerar_html_extrato(_extrato([linha], "0", "-30"), "Loja", datetime(2026, 9, 28))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Saldo final: Crédito a favor R$ 30,00" in html


def test_periodo_vazio():
    html = gerar_html_extrato(_extrato([], "40", "40"), "Loja", datetime(2026, 9, 28))
    assert "Nenhum lançamento no período." in html
