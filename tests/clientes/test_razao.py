from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.clientes.cadastro import criar_cliente
from cfauto.clientes.models import Cliente, MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import extrato, lancar_manual, saldo_apos
from cfauto.clientes.schemas import DadosCliente
from cfauto.core.errors import PermissaoNegada, ValorInvalido
from cfauto.core.models import AuditLog

DEBITO = TipoLancamento.DEBITO
CREDITO = TipoLancamento.CREDITO
COMPRA = MotivoLancamento.COMPRA_ANOTADA
PAGAMENTO = MotivoLancamento.PAGAMENTO


def _cliente(sessao, ator):
    return criar_cliente(sessao, ator, DadosCliente(nome="Ana Souza", celular="11987654321"))


def test_saldo_apos():
    assert saldo_apos(Decimal("10"), DEBITO, Decimal("5")) == Decimal("15")
    assert saldo_apos(Decimal("10"), CREDITO, Decimal("15")) == Decimal("-5")


def test_debito_e_credito_atualizam_saldo(sessao, operador):
    cid = _cliente(sessao, operador)
    l1 = lancar_manual(sessao, operador, cid, DEBITO, Decimal("120.50"), COMPRA)
    l2 = lancar_manual(sessao, operador, cid, CREDITO, Decimal("20.50"), PAGAMENTO, " PIX ")
    assert (l1.saldo_apos, l2.saldo_apos) == (Decimal("120.50"), Decimal("100.00"))
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("100.00")
    assert (l2.tipo, l2.valor, l2.motivo, l2.observacao, l2.usuario) == (
        CREDITO,
        Decimal("20.50"),
        PAGAMENTO,
        "PIX",
        "Maria",
    )


def test_credito_maior_que_divida_vira_credito_a_favor(sessao, operador):
    cid = _cliente(sessao, operador)
    lancar_manual(sessao, operador, cid, DEBITO, Decimal("50"), COMPRA)
    linha = lancar_manual(sessao, operador, cid, CREDITO, Decimal("80"), PAGAMENTO)
    assert linha.saldo_apos == Decimal("-30.00")


@pytest.mark.parametrize("valor", ["0", "-5", "0.004"])
def test_valor_invalido(sessao, admin, valor):
    cid = _cliente(sessao, admin)
    with pytest.raises(ValorInvalido, match="maior que zero"):
        lancar_manual(sessao, admin, cid, DEBITO, Decimal(valor), COMPRA)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")


def test_correcao_exige_observacao(sessao, admin):
    cid = _cliente(sessao, admin)
    with pytest.raises(ValorInvalido, match="correção"):
        lancar_manual(sessao, admin, cid, DEBITO, Decimal("10"), MotivoLancamento.CORRECAO, " ")
    linha = lancar_manual(
        sessao, admin, cid, DEBITO, Decimal("10"), MotivoLancamento.CORRECAO, "Nota 12 esquecida"
    )
    assert linha.observacao == "Nota 12 esquecida"


def test_observacao_longa_demais(sessao, admin):
    cid = _cliente(sessao, admin)
    with pytest.raises(ValorInvalido, match="200"):
        lancar_manual(sessao, admin, cid, DEBITO, Decimal("10"), COMPRA, "x" * 201)


def test_cliente_inativo_nao_recebe_lancamento(sessao, admin):
    cid = _cliente(sessao, admin)
    sessao.get(Cliente, cid).ativo = False
    with pytest.raises(ValorInvalido, match="inativo"):
        lancar_manual(sessao, admin, cid, DEBITO, Decimal("10"), COMPRA)


def test_sem_modulo_clientes(sessao, admin, estoquista):
    cid = _cliente(sessao, admin)
    with pytest.raises(PermissaoNegada):
        lancar_manual(sessao, estoquista, cid, DEBITO, Decimal("10"), COMPRA)
    with pytest.raises(PermissaoNegada):
        extrato(sessao, estoquista, cid, date(2026, 9, 1), date(2026, 9, 30))


def test_lancamento_audita(sessao, admin):
    cid = _cliente(sessao, admin)
    linha = lancar_manual(sessao, admin, cid, DEBITO, Decimal("10"), COMPRA)
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "cliente", AuditLog.acao == "lancamento")
    ).one()
    assert registro.antes == {"saldo_devedor": "0.00"}
    assert registro.depois == {
        "saldo_devedor": "10.00",
        "tipo": "DEBITO",
        "valor": "10.00",
        "motivo": "COMPRA_ANOTADA",
        "lancamento_id": linha.id,
    }


def test_extrato_periodo(sessao, admin, relogio):
    cid = _cliente(sessao, admin)
    for quando, tipo, valor in [
        (datetime(2026, 9, 1, 15, 0), DEBITO, "100"),
        (datetime(2026, 9, 10, 0, 0, 0), DEBITO, "50"),  # meia-noite do dia inicial: entra
        (datetime(2026, 9, 20, 23, 59, 59), CREDITO, "30"),  # fim do dia final: entra
        (datetime(2026, 9, 21, 0, 0, 0), CREDITO, "20"),  # dia seguinte: fora
    ]:
        relogio.definir(quando)
        lancar_manual(sessao, admin, cid, tipo, Decimal(valor), COMPRA)
    ext = extrato(sessao, admin, cid, date(2026, 9, 10), date(2026, 9, 20))
    assert ext.saldo_anterior == Decimal("100.00")
    assert [(linha.tipo, linha.valor) for linha in ext.linhas] == [
        (DEBITO, Decimal("50.00")),
        (CREDITO, Decimal("30.00")),
    ]
    assert ext.saldo_final == Decimal("120.00")
    assert (ext.cliente.codigo, ext.inicio, ext.fim) == (
        "CLI-0001",
        date(2026, 9, 10),
        date(2026, 9, 20),
    )
    assert ext.linhas[0].usuario == "Dono"


def test_extrato_sem_lancamentos_no_periodo(sessao, admin, relogio):
    cid = _cliente(sessao, admin)
    vazio = extrato(sessao, admin, cid, date(2026, 9, 1), date(2026, 9, 30))
    assert (vazio.saldo_anterior, vazio.linhas, vazio.saldo_final) == (
        Decimal("0.00"),
        (),
        Decimal("0.00"),
    )
    lancar_manual(sessao, admin, cid, DEBITO, Decimal("40"), COMPRA)  # em 23/09
    depois = extrato(sessao, admin, cid, date(2026, 10, 1), date(2026, 10, 31))
    assert (depois.saldo_anterior, depois.linhas, depois.saldo_final) == (
        Decimal("40.00"),
        (),
        Decimal("40.00"),
    )


def test_extrato_datas_invertidas(sessao, admin):
    cid = _cliente(sessao, admin)
    with pytest.raises(ValorInvalido, match="anterior"):
        extrato(sessao, admin, cid, date(2026, 9, 30), date(2026, 9, 1))


@pytest.mark.parametrize(
    "motivo",
    [
        MotivoLancamento.VENDA_CREDIARIO,
        MotivoLancamento.RECEBIMENTO,
        MotivoLancamento.CANCELAMENTO,
    ],
)
def test_lancamento_manual_recusa_motivos_do_caixa(sessao, admin, motivo):
    cid = _cliente(sessao, admin)
    with pytest.raises(ValorInvalido, match="automáticos do caixa"):
        lancar_manual(sessao, admin, cid, DEBITO, Decimal("10"), motivo)
    assert sessao.get(Cliente, cid).saldo_devedor == Decimal("0.00")
