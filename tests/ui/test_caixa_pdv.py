"""PDV: página do caixa, abertura, autorização do admin e venda pela tela."""

from decimal import Decimal

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget
from sqlalchemy import func, select

from cfauto.auth.service import NovoUsuario, autorizar_admin, criar_usuario
from cfauto.caixa.models import FormaPagamento, Venda
from cfauto.caixa.schemas import TipoDesconto
from cfauto.caixa.sessao import fechar_sessao
from cfauto.caixa.taxas import atualizar_taxa
from cfauto.caixa.venda import vendas_da_sessao
from cfauto.clientes.cadastro import criar_cliente, obter_cliente
from cfauto.clientes.models import MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar_manual
from cfauto.clientes.schemas import DadosCliente, DadosDependente
from cfauto.core.db import transacao
from cfauto.core.permissoes import Modulo
from cfauto.estoque.produtos import buscar_produtos
from cfauto.ui.caixa import abrir as modulo_abrir
from cfauto.ui.caixa import autorizacao as modulo_autorizacao
from cfauto.ui.caixa import pdv as modulo_pdv
from cfauto.ui.caixa.abrir import DialogoAbrirCaixa
from cfauto.ui.caixa.autorizacao import DialogoAutorizacao, pedir_autorizacao
from cfauto.ui.caixa.pagina import PaginaCaixa
from cfauto.ui.caixa.pdv import TelaPdv
from tests.fabricas import abrir_caixa, criar_cliente_teste, criar_produto, criar_servico

EAN = "7891234567895"


def _atores(fabrica):
    with transacao(fabrica) as s:
        admin = criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )
        operador = criar_usuario(
            s,
            admin,
            NovoUsuario(
                nome="Maria",
                login="maria",
                senha="segredo2",
                modulos=frozenset({Modulo.PDV}),
            ),
        )
    return admin, operador


def _loja(fabrica, *, estoque=Decimal("10"), abrir=True):
    """Admin, operador (só PDV), 1 produto (R$ 30, código 0001) e 1 serviço (R$ 30)."""
    admin, operador = _atores(fabrica)
    with transacao(fabrica) as s:
        produto_id = criar_produto(s, admin, ean=EAN, estoque=estoque)
        servico_id = criar_servico(s, admin)
        if abrir:
            abrir_caixa(s, admin)
    return admin, operador, produto_id, servico_id


def _nao_perguntar(texto):
    pytest.fail(f"não deveria perguntar: {texto}")


def _nao_autorizar(texto):
    pytest.fail(f"não deveria pedir autorização: {texto}")


def _tela(qtbot, fabrica, ator, *, perguntar=_nao_perguntar, autorizar=_nao_autorizar):
    tela = TelaPdv(fabrica, ator, perguntar=perguntar, autorizar=autorizar)
    qtbot.addWidget(tela)
    return tela


def _erros(monkeypatch, modulo):
    erros = []
    monkeypatch.setattr(modulo, "mostrar_erro", lambda _pai, erro: erros.append(str(erro)))
    return erros


def _qtds(tela):
    return [tela.carrinho.item(i, 1).text() for i in range(tela.carrinho.rowCount())]


def _estoque(fabrica, admin):
    with transacao(fabrica) as s:
        return buscar_produtos(s, admin, "0001")[0].estoque


def _qtd_vendas(fabrica):
    with transacao(fabrica) as s:
        return s.scalar(select(func.count()).select_from(Venda))


def test_pagina_sem_caixa_aberto_mostra_caixa_fechado_e_abre(qtbot, fabrica, relogio):
    admin, *_ = _loja(fabrica, abrir=False)
    pagina = PaginaCaixa(fabrica, admin)
    qtbot.addWidget(pagina)
    assert pagina.currentWidget() is pagina.fechado
    assert pagina.botao_abrir.text() == "Abrir caixa"
    dlg = DialogoAbrirCaixa(fabrica, admin)
    qtbot.addWidget(dlg)
    assert dlg.fundo.text() == "0,00"
    dlg.fundo.setText("150")
    dlg.abrir()
    assert dlg.result() == 1
    pagina.recarregar()
    assert pagina.currentWidget() is pagina.pdv
    assert pagina.pdv.cabecalho.text() == "CX-20260923-1000 · fundo R$ 150,00 · gaveta R$ 150,00"


def test_abrir_caixa_invalido_mostra_erro_e_nao_fecha(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_abrir)
    admin, *_ = _loja(fabrica, abrir=False)
    dlg = DialogoAbrirCaixa(fabrica, admin)
    qtbot.addWidget(dlg)
    dlg.fundo.setText("abc")
    dlg.abrir()
    assert dlg.result() == 0
    assert erros[0].startswith("Fundo de troco")
    dlg.fundo.setText("-5")
    dlg.abrir()
    assert dlg.result() == 0
    assert len(erros) == 2


def test_abrir_sugere_valor_mantido_no_ultimo_fechamento(qtbot, fabrica, relogio):
    admin, *_ = _loja(fabrica)
    with transacao(fabrica) as s:
        fechar_sessao(s, admin, Decimal("80"))
    dlg = DialogoAbrirCaixa(fabrica, admin)
    qtbot.addWidget(dlg)
    assert dlg.fundo.text() == "80,00"


def test_dialogo_autorizacao_so_aceita_admin(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_autorizacao)
    _atores(fabrica)
    dlg = DialogoAutorizacao(fabrica, "Vender sem estoque?")
    qtbot.addWidget(dlg)
    dlg.login.setText("maria")
    dlg.senha.setText("segredo2")
    dlg.confirmar()
    assert dlg.result() == 0
    assert dlg.autorizador is None
    assert "administrador" in erros[0]
    dlg.login.setText("dono")
    dlg.senha.setText("errada")
    dlg.confirmar()
    assert dlg.senha.text() == ""
    assert len(erros) == 2
    dlg.senha.setText("segredo1")
    dlg.confirmar()
    assert dlg.result() == 1
    assert dlg.autorizador.login == "dono"


@pytest.mark.parametrize("desfecho", ["aceito", "cancelado", "excecao"])
def test_pedir_autorizacao_nao_retem_a_senha_do_admin(
    qtbot, fabrica, relogio, monkeypatch, desfecho
):
    """O diálogo é filho da tela; sem limpar e apagar, a senha do admin ficaria na memória."""
    _atores(fabrica)
    pai = QWidget()
    qtbot.addWidget(pai)
    dialogos = []

    def exec_simulado(self):  # sem modal de verdade: digita e responde na hora
        dialogos.append(self)
        self.login.setText("dono")
        self.senha.setText("segredo1")
        if desfecho == "aceito":
            self.confirmar()
        elif desfecho == "cancelado":
            self.reject()
        else:
            raise RuntimeError("falha dentro do diálogo")
        return self.result()

    monkeypatch.setattr(DialogoAutorizacao, "exec", exec_simulado)
    if desfecho == "excecao":
        with pytest.raises(RuntimeError):
            pedir_autorizacao(fabrica, pai, "Vender sem estoque?")
    else:
        autorizador = pedir_autorizacao(fabrica, pai, "Vender sem estoque?")
        if desfecho == "aceito":
            assert autorizador is not None
            assert (autorizador.login, autorizador.admin) == ("dono", True)
        else:
            assert autorizador is None
    [dialogo] = dialogos
    assert dialogo.senha.text() == ""  # limpa antes mesmo de o objeto ser apagado
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert pai.findChildren(DialogoAutorizacao) == []


def test_leitor_de_codigo_soma_na_mesma_linha(qtbot, fabrica, relogio):
    _, operador, *_ = _loja(fabrica)
    tela = _tela(qtbot, fabrica, operador)
    for termo in (EAN, EAN, "0001"):
        tela.busca.setText(termo)
        tela.buscar()
    assert tela.carrinho.rowCount() == 1
    assert _qtds(tela) == ["3"]
    assert tela.busca.text() == ""
    assert "Total a cobrar R$ 90,00" in tela.totais.text()


def test_ean_inexistente_avisa_e_nao_mexe_no_carrinho(qtbot, fabrica, relogio):
    _, operador, *_ = _loja(fabrica)
    tela = _tela(qtbot, fabrica, operador)
    tela.busca.setText(EAN)
    tela.buscar()
    tela.busca.setText("999")
    tela.buscar()
    assert tela.mensagem.text() == "Nenhum produto ou serviço encontrado."
    assert _qtds(tela) == ["1"]
    assert tela.resultados.rowCount() == 0


def test_busca_por_nome_lista_produto_e_servico_e_duplo_clique_adiciona(qtbot, fabrica, relogio):
    _, operador, *_ = _loja(fabrica)
    tela = _tela(qtbot, fabrica, operador)
    tela.busca.setText("oleo")
    tela.buscar()
    assert tela.resultados.rowCount() == 2
    tipos = [tela.resultados.item(i, 0).text() for i in range(2)]
    assert sorted(tipos) == ["Produto", "Serviço"]
    linha_servico = tipos.index("Serviço")
    tela.resultados.doubleClicked.emit(tela.resultados.model().index(linha_servico, 0))
    assert tela.carrinho.item(0, 0).text() == "Troca de óleo"
    assert tela.carrinho.item(0, 2).text() == "R$ 30,00"


def test_quantidade_invalida_mostra_erro_e_restaura(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_pdv)
    _, operador, produto_id, _ = _loja(fabrica)
    tela = _tela(qtbot, fabrica, operador)
    tela.adicionar_produto(produto_id)
    tela.definir_qtd(0, "1,5")
    assert _qtds(tela) == ["1,5"]
    for texto in ("0", "-2", "abc"):
        tela.definir_qtd(0, texto)
        assert _qtds(tela) == ["1,5"]
    assert len(erros) == 3
    assert all(erro.startswith("Quantidade") for erro in erros)
    # Edição direta na célula: o handler é adiado (QTimer), então espera o efeito (o total),
    # não o texto da célula — que já é "2" antes mesmo de o handler rodar.
    tela.carrinho.item(0, 1).setText("2")
    qtbot.waitUntil(lambda: "Total a cobrar R$ 60,00" in tela.totais.text())
    assert _qtds(tela) == ["2"]
    tela.carrinho.item(0, 1).setText("abc")
    qtbot.waitUntil(lambda: len(erros) == 4)
    assert _qtds(tela) == ["2"]
    assert "Total a cobrar R$ 60,00" in tela.totais.text()


def test_remover_item_e_limpar(qtbot, fabrica, relogio):
    _, operador, produto_id, servico_id = _loja(fabrica)
    tela = _tela(qtbot, fabrica, operador)
    tela.adicionar_produto(produto_id)
    tela.adicionar_servico(servico_id)
    tela.remover_item(0)
    assert [tela.carrinho.item(0, 0).text()] == ["Troca de óleo"]
    tela.desconto.setText("5")
    tela.limpar()
    assert tela.carrinho.rowCount() == 0
    assert tela.desconto.text() == ""
    assert not tela.botao_finalizar.isEnabled()


def test_venda_mista_em_dinheiro_com_desconto_e_troco(qtbot, fabrica, relogio):
    admin, operador, produto_id, servico_id = _loja(fabrica)
    tela = _tela(qtbot, fabrica, operador)
    tela.adicionar_produto(produto_id)
    tela.adicionar_servico(servico_id)
    tela.tipo_desconto.setCurrentIndex(tela.tipo_desconto.findData(TipoDesconto.PERCENTUAL))
    tela.desconto.setText("10")
    assert tela.totais.text() == ("Subtotal R$ 60,00 · Desconto R$ 6,00 · Total a cobrar R$ 54,00")
    tela.recebido.setText("50")
    assert tela.troco.text() == "Falta R$ 4,00"
    tela.recebido.setText("100")
    assert tela.troco.text() == "Troco R$ 46,00"
    tela.finalizar()
    assert tela.mensagem.text() == "Venda nº 1 registrada."
    assert tela.carrinho.rowCount() == 0
    assert tela.desconto.text() == ""
    assert tela.cabecalho.text().endswith("gaveta R$ 154,00")
    with transacao(fabrica) as s:
        [venda] = vendas_da_sessao(s, operador)
    assert (venda.forma, venda.bruto) == (FormaPagamento.DINHEIRO, Decimal("54.00"))
    assert _estoque(fabrica, admin) == Decimal("9")


def test_recebido_vazio_permite_e_invalido_mostra_erro(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_pdv)
    _, operador, produto_id, _ = _loja(fabrica)
    tela = _tela(qtbot, fabrica, operador)
    tela.adicionar_produto(produto_id)
    tela.recebido.setText("abc")
    assert tela.troco.text() == "Troco: —"
    tela.finalizar()
    assert erros[0].startswith("Recebido")
    tela.recebido.setText("10")
    tela.finalizar()
    assert "menor" in erros[1]
    assert _qtd_vendas(fabrica) == 0
    tela.recebido.setText("")
    tela.finalizar()
    assert tela.mensagem.text() == "Venda nº 1 registrada."


def test_debito_com_repasse_soma_a_taxa_e_desabilita_recebido(qtbot, fabrica, relogio):
    admin, operador, produto_id, _ = _loja(fabrica)
    with transacao(fabrica) as s:
        atualizar_taxa(s, admin, FormaPagamento.DEBITO, Decimal("1.5"), 7, True)
    tela = _tela(qtbot, fabrica, operador)
    tela.adicionar_produto(produto_id)
    tela.recebido.setText("50")
    tela.forma.setCurrentIndex(tela.forma.findData(FormaPagamento.DEBITO))
    assert not tela.recebido.isEnabled()
    assert tela.recebido.text() == ""
    assert tela.totais.text() == (
        "Subtotal R$ 30,00 · Desconto R$ 0,00 · Taxa R$ 0,45 · Total a cobrar R$ 30,45"
    )


def test_crediario_desabilita_desconto_exige_cliente_e_confirma_limite(
    qtbot, fabrica, relogio, monkeypatch
):
    erros = _erros(monkeypatch, modulo_pdv)
    admin, operador, produto_id, _ = _loja(fabrica)
    with transacao(fabrica) as s:
        cid = criar_cliente_teste(s, admin, limite=Decimal("20.00"))
    perguntas = []
    tela = _tela(qtbot, fabrica, operador, perguntar=lambda t: perguntas.append(t) or True)
    tela.adicionar_produto(produto_id)
    tela.desconto.setText("5")
    tela.forma.setCurrentIndex(tela.forma.findData(FormaPagamento.CREDIARIO))
    assert (tela.desconto.text(), tela.desconto.isEnabled()) == ("", False)
    assert not tela.tipo_desconto.isEnabled()
    assert not tela.recebido.isEnabled()
    tela.finalizar()  # sem cliente: o serviço recusa
    assert len(erros) == 1
    assert _qtd_vendas(fabrica) == 0
    tela.definir_cliente(cid)
    assert "Disponível: R$ 20,00" in tela.painel_cliente.text()
    assert "Passa do disponível do cliente em R$ 10,00" in tela.totais.text()
    tela.finalizar()
    assert len(perguntas) == 1
    assert tela.mensagem.text() == "Venda nº 1 registrada."
    assert tela.painel_cliente.text() == "Sem cliente (consumidor final)."
    with transacao(fabrica) as s:
        assert obter_cliente(s, admin, cid).saldo_devedor == Decimal("30.00")


def test_painel_do_cliente_mostra_avisos_e_credito_a_favor(qtbot, fabrica, relogio):
    admin, operador, *_ = _loja(fabrica)
    with transacao(fabrica) as s:
        cid = criar_cliente(
            s,
            admin,
            DadosCliente(
                nome="Ana Souza",
                celular="11987654321",
                limite=None,
                observacoes="Só paga dia 10",
                dependentes=(DadosDependente("João Souza", "filho"),),
            ),
        )
        titular = criar_cliente(
            s,
            admin,
            DadosCliente(nome="Bia Lima", celular="21912345678", somente_titular=True),
        )
        lancar_manual(
            s, admin, titular, TipoLancamento.CREDITO, Decimal("50"), MotivoLancamento.PAGAMENTO
        )
    tela = _tela(qtbot, fabrica, operador)
    tela.definir_cliente(cid)
    texto = tela.painel_cliente.text()
    assert "CLI-0001 — Ana Souza · Saldo: R$ 0,00 · Disponível: Sem limite" in texto
    assert "⚠ Observações: Só paga dia 10" in texto
    assert "Dependentes: João Souza (filho)" in texto
    tela.definir_cliente(titular)
    texto = tela.painel_cliente.text()
    assert "Saldo: Crédito a favor R$ 50,00" in texto
    assert "⚠ Somente titular" in texto
    tela.definir_cliente(None)
    tela.busca_cliente.setText("bia")
    tela.busca_cliente.returnPressed.emit()
    assert "Bia Lima" in tela.painel_cliente.text()


def test_operador_sem_estoque_pede_autorizacao_do_admin(qtbot, fabrica, relogio):
    admin, operador, produto_id, _ = _loja(fabrica, estoque=Decimal("0"))
    pedidos = []
    respostas = [None, ("dono", "segredo1")]

    def autorizar(texto):
        pedidos.append(texto)
        resposta = respostas.pop(0)
        if resposta is None:
            return None
        with transacao(fabrica) as s:
            return autorizar_admin(s, *resposta)

    tela = _tela(qtbot, fabrica, operador, autorizar=autorizar)
    tela.adicionar_produto(produto_id)
    tela.finalizar()  # admin não autorizou
    assert _qtd_vendas(fabrica) == 0
    assert tela.carrinho.rowCount() == 1
    tela.finalizar()
    assert len(pedidos) == 2
    assert "administrador" in pedidos[0]
    assert tela.mensagem.text() == "Venda nº 1 registrada."
    assert _estoque(fabrica, admin) == Decimal("-1")


def test_admin_sem_estoque_confirma_na_tela(qtbot, fabrica, relogio):
    admin, _, produto_id, _ = _loja(fabrica, estoque=Decimal("0"))
    perguntas = []
    respostas = [False, True]
    tela = _tela(qtbot, fabrica, admin, perguntar=lambda t: perguntas.append(t) or respostas.pop(0))
    tela.adicionar_produto(produto_id)
    tela.finalizar()
    assert _qtd_vendas(fabrica) == 0
    tela.finalizar()
    assert tela.mensagem.text() == "Venda nº 1 registrada."
    assert "Estoque insuficiente" in perguntas[0]


def test_confirmacoes_acumulam_estoque_e_limite(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_pdv)  # sem isso, uma regressão travaria num QMessageBox
    admin, operador, produto_id, _ = _loja(fabrica, estoque=Decimal("0"))
    with transacao(fabrica) as s:
        cid = criar_cliente_teste(s, admin, limite=Decimal("20.00"))
    pedidos = []
    perguntas = []

    def autorizar(texto):
        pedidos.append(texto)
        with transacao(fabrica) as s:
            return autorizar_admin(s, "dono", "segredo1")

    tela = _tela(
        qtbot,
        fabrica,
        operador,
        perguntar=lambda t: perguntas.append(t) or True,
        autorizar=autorizar,
    )
    tela.adicionar_produto(produto_id)
    tela.forma.setCurrentIndex(tela.forma.findData(FormaPagamento.CREDIARIO))
    tela.definir_cliente(cid)
    tela.finalizar()  # falta estoque → autoriza; no reenvio, passa do limite → confirma
    assert erros == []
    assert (len(pedidos), len(perguntas)) == (1, 1)
    assert tela.mensagem.text() == "Venda nº 1 registrada."
    assert _estoque(fabrica, admin) == Decimal("-1")
    with transacao(fabrica) as s:
        assert obter_cliente(s, admin, cid).saldo_devedor == Decimal("30.00")


def test_caixa_fechado_por_outro_login_volta_para_caixa_fechado(
    qtbot, fabrica, relogio, monkeypatch
):
    erros = _erros(monkeypatch, modulo_pdv)
    admin, operador, produto_id, _ = _loja(fabrica)
    pagina = PaginaCaixa(fabrica, operador)
    qtbot.addWidget(pagina)
    assert pagina.currentWidget() is pagina.pdv
    pagina.pdv.adicionar_produto(produto_id)
    with transacao(fabrica) as s:
        fechar_sessao(s, admin, Decimal("0"))
    pagina.pdv.finalizar()
    assert "Caixa fechado" in erros[0]
    assert pagina.currentWidget() is pagina.fechado
    assert _qtd_vendas(fabrica) == 0
