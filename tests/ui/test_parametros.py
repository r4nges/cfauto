"""Configurações › Parâmetros: taxas por forma de pagamento."""

from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from sqlalchemy import func, select

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.caixa.models import FormaPagamento
from cfauto.caixa.schemas import TaxaForma
from cfauto.caixa.taxas import listar_taxas
from cfauto.core.db import transacao
from cfauto.core.models import AuditLog
from cfauto.ui import parametros as modulo_parametros
from cfauto.ui.parametros import PaginaParametros


@pytest.fixture(autouse=True)
def _sem_dialogo_modal(monkeypatch):
    """Um erro inesperado falha o teste em vez de abrir um QMessageBox modal que o travaria."""

    def falhar(_pai, erro):
        pytest.fail(f"erro mostrado ao usuário sem o teste esperar: {erro}")

    monkeypatch.setattr(modulo_parametros, "mostrar_erro", falhar)


def _admin(fabrica):
    with transacao(fabrica) as s:
        return criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )


def _taxas(fabrica, ator):
    with transacao(fabrica) as s:
        return {t.forma: t for t in listar_taxas(s, ator)}


def test_parametros_lista_e_salva_so_o_que_mudou(qtbot, fabrica, relogio):
    admin = _admin(fabrica)
    pagina = PaginaParametros(fabrica, admin)
    qtbot.addWidget(pagina)
    tabela = pagina.tabela_taxas
    assert [tabela.item(i, 0).text() for i in range(tabela.rowCount())] == [
        "Dinheiro",
        "PIX",
        "Débito",
        "Crédito",
    ]
    assert (tabela.item(2, 1).text(), tabela.item(2, 2).text()) == ("1,50", "7")
    assert tabela.item(2, 3).checkState() == Qt.CheckState.Unchecked
    tabela.item(2, 1).setText("2,5")
    tabela.item(2, 2).setText("0")
    tabela.item(2, 3).setCheckState(Qt.CheckState.Checked)
    pagina.salvar_taxas()
    debito = _taxas(fabrica, admin)[FormaPagamento.DEBITO]
    assert debito == TaxaForma(FormaPagamento.DEBITO, Decimal("2.50"), 0, True)
    with transacao(fabrica) as s:
        alteracoes = s.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.entidade == "taxa_pagamento")
        )
    assert alteracoes == 1


def test_parametros_valor_invalido_nao_salva_nada(qtbot, fabrica, relogio, monkeypatch):
    erros = []
    monkeypatch.setattr(
        modulo_parametros, "mostrar_erro", lambda _pai, erro: erros.append(str(erro))
    )
    admin = _admin(fabrica)
    pagina = PaginaParametros(fabrica, admin)
    qtbot.addWidget(pagina)
    tabela = pagina.tabela_taxas
    tabela.item(1, 1).setText("0,99")  # PIX válido: não pode ser gravado sozinho
    tabela.item(2, 1).setText("abc")
    pagina.salvar_taxas()
    assert erros[0].startswith("Débito")
    tabela.item(2, 1).setText("1,5")
    tabela.item(2, 2).setText("1,5")
    pagina.salvar_taxas()
    assert "inteiro" in erros[1]
    taxas = _taxas(fabrica, admin)
    assert taxas[FormaPagamento.PIX].pct == Decimal("0.00")
    assert taxas[FormaPagamento.DEBITO].dias == 7


def _auditorias(fabrica):
    with transacao(fabrica) as s:
        return s.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.entidade == "taxa_pagamento")
        )


def test_parametros_sem_alteracao_nao_grava_nem_audita(qtbot, fabrica, relogio):
    admin = _admin(fabrica)
    pagina = PaginaParametros(fabrica, admin)
    qtbot.addWidget(pagina)
    antes = _auditorias(fabrica)
    pagina.salvar_taxas()
    assert pagina._mensagem.text() == "Nenhuma alteração."
    # 1,501 arredonda para os mesmos 1,50 já gravados: também não é alteração.
    pagina.tabela_taxas.item(2, 1).setText("1,501")
    pagina.salvar_taxas()
    assert pagina._mensagem.text() == "Nenhuma alteração."
    assert _auditorias(fabrica) == antes


def test_parametros_dias_acima_do_teto_mostra_o_erro_do_dominio(
    qtbot, fabrica, relogio, monkeypatch
):
    erros = []
    monkeypatch.setattr(
        modulo_parametros, "mostrar_erro", lambda _pai, erro: erros.append(str(erro))
    )
    admin = _admin(fabrica)
    pagina = PaginaParametros(fabrica, admin)
    qtbot.addWidget(pagina)
    pagina.tabela_taxas.item(2, 2).setText("366")
    pagina.salvar_taxas()
    assert erros == ["Os dias até a liquidação não podem passar de 365."]
    assert _taxas(fabrica, admin)[FormaPagamento.DEBITO].dias == 7
