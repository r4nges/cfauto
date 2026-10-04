from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QDate

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.clientes.cadastro import buscar_clientes, criar_cliente
from cfauto.clientes.models import MOTIVOS_MANUAIS, MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar_manual
from cfauto.clientes.schemas import DadosCliente
from cfauto.core import config
from cfauto.core.db import transacao
from cfauto.ui.clientes import extrato as modulo_extrato
from cfauto.ui.clientes import lancamento as modulo_lancamento
from cfauto.ui.clientes.extrato import DialogoExtrato
from cfauto.ui.clientes.lancamento import DialogoLancamento
from cfauto.ui.clientes.tela import TelaClientes


def _admin(fabrica):
    with transacao(fabrica) as s:
        return criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )


def _cliente(fabrica, ator):
    with transacao(fabrica) as s:
        cid = criar_cliente(s, ator, DadosCliente(nome="Ana Souza", celular="11987654321"))
        (resumo,) = buscar_clientes(s, ator, "")
    return cid, resumo


def _saldo(fabrica, ator):
    with transacao(fabrica) as s:
        return buscar_clientes(s, ator, "")[0].saldo_devedor


def test_lancamento_mostra_previa_e_grava(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    _, resumo = _cliente(fabrica, ator)
    dlg = DialogoLancamento(fabrica, ator, resumo)
    qtbot.addWidget(dlg)
    assert dlg.previa.text() == "Saldo após: —"
    dlg.aumentar.setChecked(True)
    dlg.valor.setText("1.234,56")
    assert dlg.previa.text() == "Saldo após: R$ 1.234,56"
    dlg.salvar()
    assert dlg.result() == 1
    assert _saldo(fabrica, ator) == Decimal("1234.56")


def test_abater_mais_que_a_divida_mostra_credito_a_favor(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    _, resumo = _cliente(fabrica, ator)
    dlg = DialogoLancamento(fabrica, ator, resumo)
    qtbot.addWidget(dlg)
    dlg.abater.setChecked(True)
    dlg.valor.setText("50")
    assert dlg.tipo() == TipoLancamento.CREDITO
    assert dlg.previa.text() == "Saldo após: Crédito a favor R$ 50,00"


def test_lancamento_invalido_mostra_erro_e_nao_fecha(qtbot, fabrica, relogio, monkeypatch):
    erros = []
    monkeypatch.setattr(
        modulo_lancamento, "mostrar_erro", lambda _pai, erro: erros.append(str(erro))
    )
    ator = _admin(fabrica)
    _, resumo = _cliente(fabrica, ator)
    dlg = DialogoLancamento(fabrica, ator, resumo)
    qtbot.addWidget(dlg)
    dlg.valor.setText("abc")
    assert dlg.previa.text() == "Saldo após: —"
    dlg.salvar()
    assert dlg.result() == 0
    assert erros[0].startswith("Valor")
    dlg.valor.setText("10")
    dlg.motivo.setCurrentIndex(MOTIVOS_MANUAIS.index(MotivoLancamento.CORRECAO))
    dlg.salvar()
    assert "correção" in erros[1]
    assert _saldo(fabrica, ator) == Decimal("0.00")


def test_lancamento_valor_arredonda_a_zero_mostra_previa_vazia(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    _, resumo = _cliente(fabrica, ator)
    dlg = DialogoLancamento(fabrica, ator, resumo)
    qtbot.addWidget(dlg)
    dlg.aumentar.setChecked(True)
    dlg.valor.setText("0,004")
    assert dlg.previa.text() == "Saldo após: —"


def test_lancamento_so_lista_motivos_manuais(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    _, resumo = _cliente(fabrica, ator)
    dlg = DialogoLancamento(fabrica, ator, resumo)
    qtbot.addWidget(dlg)
    motivos = [dlg.motivo.itemData(i) for i in range(dlg.motivo.count())]
    assert motivos == list(MOTIVOS_MANUAIS)


def test_extrato_mostra_periodo_padrao_e_imprime(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    cid, _ = _cliente(fabrica, ator)
    with transacao(fabrica) as s:
        config.definir(s, "empresa.nome", "Loja Teste")
        relogio.definir(datetime(2026, 6, 1, 9, 0))  # antes dos 90 dias: vira saldo anterior
        lancar_manual(
            s, ator, cid, TipoLancamento.DEBITO, Decimal("100"), MotivoLancamento.COMPRA_ANOTADA
        )
        relogio.definir(datetime(2026, 9, 20, 15, 0))
        lancar_manual(
            s, ator, cid, TipoLancamento.CREDITO, Decimal("30"), MotivoLancamento.PAGAMENTO, "PIX"
        )
    relogio.definir(datetime(2026, 9, 23, 10, 0))
    dlg = DialogoExtrato(fabrica, ator, cid)
    qtbot.addWidget(dlg)
    assert dlg.inicio.date().toString("dd/MM/yyyy") == "25/06/2026"
    assert dlg.fim.date().toString("dd/MM/yyyy") == "23/09/2026"
    assert dlg.tabela.rowCount() == 1
    assert dlg.tabela.item(0, 1).text() == "Pagamento — PIX"
    assert dlg.tabela.item(0, 3).text() == "R$ 30,00"
    assert dlg.saldo_anterior.text() == "Saldo anterior: R$ 100,00"
    assert dlg.saldo_final.text() == "Saldo final: R$ 70,00"
    previas = []
    dlg._abrir_previa = lambda documento: previas.append(documento.toPlainText())
    dlg.imprimir()
    assert "Loja Teste" in previas[0]
    assert "Extrato do cliente" in previas[0]


def test_extrato_imprime_periodo_atual_mesmo_sem_atualizar(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    cid, _ = _cliente(fabrica, ator)
    with transacao(fabrica) as s:
        config.definir(s, "empresa.nome", "Loja Teste")
        relogio.definir(datetime(2026, 6, 1, 9, 0))
        lancar_manual(
            s, ator, cid, TipoLancamento.DEBITO, Decimal("100"), MotivoLancamento.COMPRA_ANOTADA
        )
        relogio.definir(datetime(2026, 9, 20, 15, 0))
        lancar_manual(
            s, ator, cid, TipoLancamento.CREDITO, Decimal("30"), MotivoLancamento.PAGAMENTO, "PIX"
        )
    relogio.definir(datetime(2026, 9, 23, 10, 0))
    dlg = DialogoExtrato(fabrica, ator, cid)
    qtbot.addWidget(dlg)
    # Muda o período nos campos de data SEM clicar em "Atualizar".
    dlg.inicio.setDate(QDate(2026, 5, 1))
    dlg.fim.setDate(QDate(2026, 6, 15))
    previas = []
    dlg._abrir_previa = lambda documento: previas.append(documento.toPlainText())
    dlg.imprimir()
    assert len(previas) == 1
    assert "R$ 100,00" in previas[0]
    assert "R$ 30,00" not in previas[0]
    assert dlg.inicio.date().toString("dd/MM/yyyy") == "01/05/2026"
    assert dlg.fim.date().toString("dd/MM/yyyy") == "15/06/2026"


def test_extrato_nao_imprime_quando_periodo_invalido(qtbot, fabrica, relogio, monkeypatch):
    ator = _admin(fabrica)
    cid, _ = _cliente(fabrica, ator)
    dlg = DialogoExtrato(fabrica, ator, cid)
    qtbot.addWidget(dlg)
    erros = []
    monkeypatch.setattr(modulo_extrato, "mostrar_erro", lambda _pai, erro: erros.append(str(erro)))
    dlg.inicio.setDate(QDate(2026, 9, 23))
    dlg.fim.setDate(QDate(2026, 1, 1))  # fim antes do início: recarregar() falha
    previas = []
    dlg._abrir_previa = lambda documento: previas.append(documento.toPlainText())
    dlg.imprimir()
    assert not previas
    assert erros


def test_tela_tem_botoes_de_lancamento_e_extrato(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    tela = TelaClientes(fabrica, ator)
    qtbot.addWidget(tela)
    assert (tela.botao_lancamento.text(), tela.botao_extrato.text()) == ("Lançamento", "Extrato")
    assert not tela.botao_lancamento.isHidden()
