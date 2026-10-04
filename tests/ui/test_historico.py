"""Histórico: vendas e sessões fechadas, com filtros e detalhe."""

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import QDate

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.caixa.models import FormaPagamento, TipoVenda
from cfauto.caixa.recebimento import registrar_recebimento
from cfauto.caixa.schemas import ItemVenda, NovaVenda
from cfauto.caixa.sessao import fechar_sessao
from cfauto.caixa.venda import cancelar_venda, registrar_venda
from cfauto.core.db import transacao
from cfauto.ui.historico import tela as modulo_historico
from cfauto.ui.historico.tela import TelaHistorico
from tests.fabricas import abrir_caixa, criar_cliente_teste, criar_produto, criar_servico


@pytest.fixture(autouse=True)
def _sem_dialogo_modal(monkeypatch):
    """Um erro inesperado falha o teste em vez de abrir um QMessageBox modal que o travaria."""

    def falhar(_pai, erro):
        pytest.fail(f"erro mostrado ao usuário sem o teste esperar: {erro}")

    monkeypatch.setattr(modulo_historico, "mostrar_erro", falhar)


def _venda(s, ator, forma, *, produto_id=None, servico_id=None, cliente_id=None):
    return registrar_venda(
        s,
        ator,
        NovaVenda(
            itens=(ItemVenda(Decimal(1), produto_id=produto_id, servico_id=servico_id),),
            forma=forma,
            cliente_id=cliente_id,
        ),
    )


def _dados(fabrica, relogio):
    """Sessão fechada: dinheiro, débito, crediário (Ana), recebimento PIX (Ana) e uma
    venda cancelada. Depois, uma sessão aberta com uma venda que não pode aparecer."""
    with transacao(fabrica) as s:
        admin = criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )
        pid = criar_produto(s, admin)
        sid = criar_servico(s, admin)
        cid = criar_cliente_teste(s, admin)
        abrir_caixa(s, admin)
        _venda(s, admin, FormaPagamento.DINHEIRO, produto_id=pid)
        _venda(s, admin, FormaPagamento.DEBITO, servico_id=sid)
        _venda(s, admin, FormaPagamento.CREDIARIO, produto_id=pid, cliente_id=cid)
        registrar_recebimento(s, admin, cid, Decimal("10"), FormaPagamento.PIX)
        cancelada = _venda(s, admin, FormaPagamento.DINHEIRO, produto_id=pid)
        cancelar_venda(s, admin, cancelada, "Teste")
        fechar_sessao(s, admin, Decimal("0"))
    relogio.avancar(hours=1)
    with transacao(fabrica) as s:
        abrir_caixa(s, admin)
        _venda(s, admin, FormaPagamento.DINHEIRO, produto_id=pid)
    return admin


def _coluna(tabela, coluna):
    return [tabela.item(i, coluna).text() for i in range(tabela.rowCount())]


def _linha(tabela, linha):
    return [tabela.item(linha, j).text() for j in range(tabela.columnCount())]


def test_historico_lista_so_sessoes_fechadas_com_filtros(qtbot, fabrica, relogio):
    admin = _dados(fabrica, relogio)
    tela = TelaHistorico(fabrica, admin)
    qtbot.addWidget(tela)
    assert [tela.tabText(i) for i in range(tela.count())] == ["Vendas", "Sessões"]
    assert tela.inicio.date().toString("dd/MM/yyyy") == "01/09/2026"
    assert _coluna(tela.vendas, 0) == ["CX-20260923-1000"] * 4
    assert sorted(_coluna(tela.vendas, 5)) == ["Crediário", "Dinheiro", "Débito", "PIX"]

    tela.incluir_canceladas.setChecked(True)
    tela.recarregar()
    assert tela.vendas.rowCount() == 5
    assert _coluna(tela.vendas, 10).count("Cancelada") == 1
    tela.incluir_canceladas.setChecked(False)

    tela.forma.setCurrentIndex(tela.forma.findData(FormaPagamento.DEBITO))
    tela.recarregar()
    assert _linha(tela.vendas, 0)[2:] == [
        "Troca de óleo",
        "",
        "Venda",
        "Débito",
        "R$ 30,00",
        "R$ 0,45",
        "R$ 29,55",
        "7",
        "Ativa",
    ]
    tela.forma.setCurrentIndex(tela.forma.findData(FormaPagamento.CREDIARIO))
    tela.recarregar()
    assert _linha(tela.vendas, 0)[9] == "—"
    tela.forma.setCurrentIndex(0)

    tela.tipo.setCurrentIndex(tela.tipo.findData(TipoVenda.RECEBIMENTO))
    tela.recarregar()
    assert _coluna(tela.vendas, 2) == ["RECEBIMENTO DE CONTA / FIADO"]
    tela.tipo.setCurrentIndex(0)

    tela.cliente.setText("ana")
    tela.recarregar()
    assert sorted(_coluna(tela.vendas, 5)) == ["Crediário", "PIX"]
    assert set(_coluna(tela.vendas, 3)) == {"Ana Souza"}


def test_historico_detalhe_de_venda_e_de_sessao(qtbot, fabrica, relogio):
    admin = _dados(fabrica, relogio)
    tela = TelaHistorico(fabrica, admin)
    qtbot.addWidget(tela)
    exibidos = []
    tela._exibir = lambda titulo, texto: exibidos.append((titulo, texto))
    tela.forma.setCurrentIndex(tela.forma.findData(FormaPagamento.DEBITO))
    tela.recarregar()
    tela.vendas.doubleClicked.emit(tela.vendas.model().index(0, 0))
    titulo, texto = exibidos[0]
    assert titulo.startswith("Venda nº")
    assert "Troca de óleo" in texto
    assert "Usuário: Dono" in texto

    assert tela.sessoes.rowCount() == 1
    assert _linha(tela.sessoes, 0) == [
        "CX-20260923-1000",
        "23/09/2026 10:00",
        "23/09/2026 10:00",
        "Dono",
        "Dono",
        "R$ 100,00",
        "R$ 90,00",
        "R$ 130,00",
        "R$ 0,00",
        "R$ 130,00",
    ]
    tela.sessoes.doubleClicked.emit(tela.sessoes.model().index(0, 0))
    assert exibidos[1][0] == "Sessão CX-20260923-1000"
    assert "Gaveta: R$ 130,00" in exibidos[1][1]
    assert "Sangria: R$ 130,00" in exibidos[1][1]


def test_historico_periodo_invertido_mostra_erro(qtbot, fabrica, relogio, monkeypatch):
    erros = []
    monkeypatch.setattr(
        modulo_historico, "mostrar_erro", lambda _pai, erro: erros.append(str(erro))
    )
    admin = _dados(fabrica, relogio)
    tela = TelaHistorico(fabrica, admin)
    qtbot.addWidget(tela)
    fim = date(2026, 9, 1)
    tela.fim.setDate(QDate(fim.year, fim.month, fim.day))
    tela.inicio.setDate(QDate(2026, 9, 20))
    tela.recarregar()
    assert "A data final é anterior à inicial." in erros
