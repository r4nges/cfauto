from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.clientes.cadastro import (
    buscar_clientes,
    criar_cliente,
    excluir_cliente,
    inativar_cliente,
    reativar_cliente,
)
from cfauto.clientes.models import Cliente, ClienteDependente, MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar_manual
from cfauto.clientes.schemas import DadosCliente, DadosDependente
from cfauto.core.errors import (
    ClienteComHistorico,
    ClienteComSaldo,
    PermissaoNegada,
    ValorInvalido,
)
from cfauto.core.models import AuditLog


def _cliente(sessao, ator, nome="Ana Souza", **campos):
    return criar_cliente(sessao, ator, DadosCliente(nome=nome, celular="11987654321", **campos))


def _lancar(sessao, ator, cid, tipo, valor):
    motivo = MotivoLancamento.COMPRA_ANOTADA
    lancar_manual(sessao, ator, cid, tipo, Decimal(valor), motivo)


def _codigos(sessao, ator, **kw):
    return [r.codigo for r in buscar_clientes(sessao, ator, "", **kw)]


def test_inativar_esconde_da_busca_e_reativar_volta(sessao, admin):
    cid = _cliente(sessao, admin)
    inativar_cliente(sessao, admin, cid)
    assert _codigos(sessao, admin) == []
    assert _codigos(sessao, admin, incluir_inativos=True) == ["CLI-0001"]
    with pytest.raises(ValorInvalido, match="já está inativo"):
        inativar_cliente(sessao, admin, cid)
    reativar_cliente(sessao, admin, cid)
    assert _codigos(sessao, admin) == ["CLI-0001"]
    with pytest.raises(ValorInvalido, match="já está ativo"):
        reativar_cliente(sessao, admin, cid)
    acoes = sessao.scalars(
        select(AuditLog.acao).where(AuditLog.entidade == "cliente").order_by(AuditLog.id)
    ).all()
    assert acoes == ["criar", "inativar", "reativar"]


def test_inativar_com_saldo_bloqueia(sessao, admin):
    cid = _cliente(sessao, admin)
    _lancar(sessao, admin, cid, TipoLancamento.DEBITO, "10")
    with pytest.raises(ClienteComSaldo, match="deve R\\$ 10,00"):
        inativar_cliente(sessao, admin, cid)
    _lancar(sessao, admin, cid, TipoLancamento.CREDITO, "30")
    with pytest.raises(ClienteComSaldo, match="crédito a favor de R\\$ 20,00"):
        inativar_cliente(sessao, admin, cid)
    _lancar(sessao, admin, cid, TipoLancamento.DEBITO, "20")
    inativar_cliente(sessao, admin, cid)
    assert sessao.get(Cliente, cid).ativo is False


def test_excluir_sem_historico(sessao, admin):
    cid = _cliente(sessao, admin, dependentes=(DadosDependente("João Souza"),))
    excluir_cliente(sessao, admin, cid)
    assert sessao.get(Cliente, cid) is None
    assert sessao.scalars(select(ClienteDependente)).all() == []
    registro = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "cliente", AuditLog.acao == "excluir")
    ).one()
    assert (registro.antes["codigo"], registro.depois) == ("CLI-0001", None)
    # Código nunca reaproveitado.
    novo = _cliente(sessao, admin, nome="Bia Lima")
    assert sessao.get(Cliente, novo).codigo == "CLI-0002"


def test_excluir_com_saldo_ou_historico_bloqueia(sessao, admin):
    cid = _cliente(sessao, admin)
    _lancar(sessao, admin, cid, TipoLancamento.DEBITO, "10")
    with pytest.raises(ClienteComSaldo):
        excluir_cliente(sessao, admin, cid)
    _lancar(sessao, admin, cid, TipoLancamento.CREDITO, "10")
    with pytest.raises(ClienteComHistorico, match="Inativar"):
        excluir_cliente(sessao, admin, cid)


def test_so_admin(sessao, admin, operador):
    cid = _cliente(sessao, admin)
    for acao in (inativar_cliente, reativar_cliente, excluir_cliente):
        with pytest.raises(PermissaoNegada):
            acao(sessao, operador, cid)
