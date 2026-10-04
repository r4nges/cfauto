from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.caixa.calculo import resumo_de_json
from cfauto.caixa.models import SessaoCaixa, StatusSessao
from cfauto.caixa.sessao import (
    abrir_sessao,
    exigir_sessao_aberta,
    fechar_sessao,
    nome_usuario,
    previa_fechamento,
    sessao_aberta,
    sugestao_fundo,
)
from cfauto.core.errors import PermissaoNegada, SessaoFechada, SessaoJaAberta, ValorInvalido
from cfauto.core.models import AuditLog
from tests.fabricas import abrir_caixa


def test_sem_sessao_aberta(sessao, operador):
    assert sessao_aberta(sessao, operador) is None
    with pytest.raises(SessaoFechada, match="Caixa fechado"):
        exigir_sessao_aberta(sessao)


def test_abrir_sessao_gera_protocolo_e_painel(sessao, operador):
    painel = abrir_sessao(sessao, operador, Decimal("150"))
    assert painel.protocolo == "CX-20260923-1000"
    assert painel.aberta_em == datetime(2026, 9, 23, 10, 0)
    assert painel.aberta_por == "Maria"
    assert painel.fundo_troco == Decimal("150.00")
    assert painel.gaveta == Decimal("150.00")
    assert painel.qtd_vendas == 0
    assert sessao_aberta(sessao, operador) == painel
    registro = exigir_sessao_aberta(sessao)
    assert (registro.status, registro.aberta_por) == (StatusSessao.ABERTA, operador.id)


def test_so_uma_sessao_aberta(sessao, operador):
    abrir_caixa(sessao, operador)
    with pytest.raises(SessaoJaAberta):
        abrir_sessao(sessao, operador, Decimal("0"))


def test_fundo_negativo_recusado(sessao, operador):
    with pytest.raises(ValorInvalido, match="negativo"):
        abrir_sessao(sessao, operador, Decimal("-0.01"))
    assert sessao_aberta(sessao, operador) is None


def test_protocolo_que_colide_no_mesmo_minuto_ganha_sufixo(sessao, operador, relogio):
    abrir_caixa(sessao, operador)
    fechar_sessao(sessao, operador, Decimal("100"))
    relogio.avancar(seconds=30)
    assert abrir_sessao(sessao, operador, Decimal("0")).protocolo == "CX-20260923-1000-2"
    fechar_sessao(sessao, operador, Decimal("0"))
    assert abrir_sessao(sessao, operador, Decimal("0")).protocolo == "CX-20260923-1000-3"
    fechar_sessao(sessao, operador, Decimal("0"))
    relogio.avancar(minutes=1)
    assert abrir_sessao(sessao, operador, Decimal("0")).protocolo == "CX-20260923-1001"


def test_sugestao_de_fundo_e_o_valor_mantido_da_ultima_sessao(sessao, operador, relogio):
    assert sugestao_fundo(sessao, operador) == Decimal("0")
    abrir_caixa(sessao, operador, Decimal("200"))
    fechar_sessao(sessao, operador, Decimal("80"))
    assert sugestao_fundo(sessao, operador) == Decimal("80.00")
    relogio.avancar(hours=1)
    abrir_caixa(sessao, operador, Decimal("80"))
    fechar_sessao(sessao, operador, Decimal("50"))
    assert sugestao_fundo(sessao, operador) == Decimal("50.00")


def test_previa_sem_vendas(sessao, operador):
    abrir_caixa(sessao, operador, Decimal("100"))
    resumo = previa_fechamento(sessao, operador)
    assert resumo.fundo_troco == Decimal("100.00")
    assert resumo.vendas == {}
    assert resumo.recebimentos == {}
    assert (resumo.canceladas_qtd, resumo.canceladas_bruto) == (0, Decimal("0"))
    assert (resumo.total_vendido, resumo.dinheiro, resumo.gaveta) == (
        Decimal("0"),
        Decimal("0"),
        Decimal("100.00"),
    )


def test_fechar_grava_resumo_sangria_e_status(sessao, operador, relogio):
    painel = abrir_caixa(sessao, operador, Decimal("100"))
    relogio.avancar(hours=8)
    fechamento = fechar_sessao(sessao, operador, Decimal("30"))
    assert fechamento.protocolo == painel.protocolo
    assert (fechamento.valor_mantido, fechamento.sangria) == (Decimal("30.00"), Decimal("70.00"))
    assert fechamento.resumo.gaveta == Decimal("100.00")
    registro = sessao.get(SessaoCaixa, painel.id)
    assert registro.status == StatusSessao.FECHADA
    assert registro.fechada_em == datetime(2026, 9, 23, 18, 0)
    assert registro.fechada_por == operador.id
    assert (registro.valor_mantido, registro.sangria) == (Decimal("30.00"), Decimal("70.00"))
    assert resumo_de_json(registro.resumo_json) == fechamento.resumo
    assert sessao_aberta(sessao, operador) is None


def test_sessao_fechada_nao_aceita_nova_operacao(sessao, operador):
    abrir_caixa(sessao, operador)
    fechar_sessao(sessao, operador, Decimal("0"))
    with pytest.raises(SessaoFechada):
        previa_fechamento(sessao, operador)
    with pytest.raises(SessaoFechada):
        fechar_sessao(sessao, operador, Decimal("0"))


@pytest.mark.parametrize("mantido", ["-0.01", "100.01"])
def test_valor_mantido_fora_da_faixa(sessao, operador, mantido):
    abrir_caixa(sessao, operador, Decimal("100"))
    with pytest.raises(ValorInvalido):
        fechar_sessao(sessao, operador, Decimal(mantido))
    assert sessao_aberta(sessao, operador) is not None


def test_exige_modulo_pdv(sessao, admin, estoquista):
    with pytest.raises(PermissaoNegada):
        abrir_sessao(sessao, estoquista, Decimal("0"))
    with pytest.raises(PermissaoNegada):
        sessao_aberta(sessao, estoquista)
    with pytest.raises(PermissaoNegada):
        sugestao_fundo(sessao, estoquista)
    abrir_caixa(sessao, admin)
    with pytest.raises(PermissaoNegada):
        previa_fechamento(sessao, estoquista)
    with pytest.raises(PermissaoNegada):
        fechar_sessao(sessao, estoquista, Decimal("0"))


def test_auditoria_de_abrir_e_fechar(sessao, operador):
    painel = abrir_caixa(sessao, operador, Decimal("100"))
    fechar_sessao(sessao, operador, Decimal("40"))
    registros = sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "sessao_caixa").order_by(AuditLog.id)
    ).all()
    assert [(r.acao, r.entidade_id, r.usuario_id) for r in registros] == [
        ("abrir", str(painel.id), operador.id),
        ("fechar", str(painel.id), operador.id),
    ]
    assert registros[0].depois["fundo_troco"] == "100.00"
    assert registros[1].depois["sangria"] == "60.00"
    assert registros[1].depois["status"] == "FECHADA"


def test_nome_usuario_existente_desconhecido_e_nulo(sessao, operador):
    assert nome_usuario(sessao, operador.id) == "Maria"
    assert nome_usuario(sessao, operador.id + 1000) is None
    assert nome_usuario(sessao, None) is None
