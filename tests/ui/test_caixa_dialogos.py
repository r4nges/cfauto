"""Diálogos do caixa: receber crediário, fechar caixa e vendas da sessão."""

from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from cfauto.auth.service import NovoUsuario, autorizar_admin, criar_usuario
from cfauto.caixa.models import FormaPagamento
from cfauto.caixa.recebimento import registrar_recebimento
from cfauto.caixa.schemas import ItemVenda, NovaVenda, ResumoSessao, TotaisForma
from cfauto.caixa.sessao import fechar_sessao, sessao_aberta, sugestao_fundo
from cfauto.caixa.venda import registrar_venda
from cfauto.clientes.cadastro import obter_cliente
from cfauto.clientes.models import MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar_manual
from cfauto.core.db import transacao
from cfauto.core.errors import SessaoFechada
from cfauto.core.permissoes import Modulo
from cfauto.estoque.produtos import buscar_produtos
from cfauto.ui.caixa import fechamento as modulo_fechamento
from cfauto.ui.caixa import pdv as modulo_pdv
from cfauto.ui.caixa import recebimento as modulo_recebimento
from cfauto.ui.caixa import vendas_sessao as modulo_vendas
from cfauto.ui.caixa.fechamento import DialogoFechamento
from cfauto.ui.caixa.formatos import BuscaCliente, descrever_resumo
from cfauto.ui.caixa.pdv import TelaPdv
from cfauto.ui.caixa.recebimento import DialogoRecebimento
from cfauto.ui.caixa.vendas_sessao import DialogoVendasSessao
from tests.fabricas import abrir_caixa, criar_cliente_teste, criar_produto, criar_servico


@pytest.fixture(autouse=True)
def _sem_dialogo_modal(monkeypatch):
    """Um erro inesperado falha o teste em vez de abrir um QMessageBox modal que o travaria."""

    def falhar(_pai, erro):
        pytest.fail(f"erro mostrado ao usuário sem o teste esperar: {erro}")

    for modulo in (modulo_pdv, modulo_recebimento, modulo_fechamento, modulo_vendas):
        monkeypatch.setattr(modulo, "mostrar_erro", falhar)


def _loja(fabrica):
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
        produto_id = criar_produto(s, admin)
        servico_id = criar_servico(s, admin)
        abrir_caixa(s, admin)
    return admin, operador, produto_id, servico_id


def _vender(fabrica, ator, *, produto_id=None, servico_id=None, forma=FormaPagamento.DINHEIRO):
    with transacao(fabrica) as s:
        return registrar_venda(
            s,
            ator,
            NovaVenda(
                itens=(ItemVenda(Decimal(1), produto_id=produto_id, servico_id=servico_id),),
                forma=forma,
            ),
        )


def _saldo(fabrica, ator, cliente_id):
    with transacao(fabrica) as s:
        return obter_cliente(s, ator, cliente_id).saldo_devedor


def _estoque(fabrica, admin):
    with transacao(fabrica) as s:
        return buscar_produtos(s, admin, "0001")[0].estoque


def _erros(monkeypatch, modulo):
    erros = []
    monkeypatch.setattr(modulo, "mostrar_erro", lambda _pai, erro: erros.append(str(erro)))
    return erros


def _nao_perguntar(texto):
    pytest.fail(f"não deveria perguntar: {texto}")


def _nao_autorizar(texto):
    pytest.fail(f"não deveria pedir autorização: {texto}")


def _autorizar_como_admin(fabrica, pedidos):
    def autorizar(texto):
        pedidos.append(texto)
        with transacao(fabrica) as s:
            return autorizar_admin(s, "dono", "segredo1")

    return autorizar


def test_recebimento_abate_divida_e_avisa_excedente(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_recebimento)
    admin, operador, *_ = _loja(fabrica)
    with transacao(fabrica) as s:
        cid = criar_cliente_teste(s, admin)
        lancar_manual(
            s, admin, cid, TipoLancamento.DEBITO, Decimal("100"), MotivoLancamento.COMPRA_ANOTADA
        )
    dlg = DialogoRecebimento(fabrica, operador, perguntar=_nao_perguntar)
    qtbot.addWidget(dlg)
    dlg.definir_cliente(cid)
    dlg.valor.setText("40")
    dlg.forma.setCurrentIndex(dlg.forma.findData(FormaPagamento.PIX))
    dlg.salvar()
    assert dlg.result() == 1
    assert _saldo(fabrica, admin, cid) == Decimal("60.00")

    perguntas = []
    respostas = [False, True]
    dlg = DialogoRecebimento(
        fabrica, operador, perguntar=lambda t: perguntas.append(t) or respostas.pop(0)
    )
    qtbot.addWidget(dlg)
    dlg.definir_cliente(cid)
    dlg.valor.setText("80")
    dlg.recebido.setText("50")
    dlg.salvar()
    assert "menor" in erros[0]
    assert perguntas == []
    dlg.recebido.setText("100")
    dlg.salvar()  # recusa o excedente
    assert dlg.result() == 0
    assert _saldo(fabrica, admin, cid) == Decimal("60.00")
    assert "crédito a favor" in perguntas[0]
    assert "R$ 20,00" in perguntas[0]
    dlg.salvar()  # aceita
    assert dlg.result() == 1
    assert dlg.venda_id is not None
    assert _saldo(fabrica, admin, cid) == Decimal("-20.00")


def test_recebimento_sem_cliente_mostra_erro(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_recebimento)
    _, operador, *_ = _loja(fabrica)
    dlg = DialogoRecebimento(fabrica, operador, perguntar=_nao_perguntar)
    qtbot.addWidget(dlg)
    dlg.valor.setText("10")
    dlg.salvar()
    assert erros == ["Selecione o cliente."]
    assert dlg.result() == 0


def test_fechamento_mostra_resumo_sangria_e_fecha(qtbot, fabrica, relogio):
    _, operador, produto_id, servico_id = _loja(fabrica)
    _vender(fabrica, operador, produto_id=produto_id)
    _vender(fabrica, operador, servico_id=servico_id, forma=FormaPagamento.PIX)
    perguntas = []
    dlg = DialogoFechamento(fabrica, operador, perguntar=lambda t: perguntas.append(t) or True)
    qtbot.addWidget(dlg)
    texto = dlg.resumo.text()
    assert "Dinheiro: 1 · bruto R$ 30,00" in texto
    assert "PIX: 1 · bruto R$ 30,00" in texto
    assert "Gaveta: R$ 130,00" in texto
    assert dlg.valor_mantido.text() == "100,00"
    assert dlg.sangria.text() == "Sangria: R$ 30,00"
    dlg.valor_mantido.setText("200")
    assert dlg.sangria.text().startswith("Sangria: —")
    dlg.valor_mantido.setText("50")
    assert dlg.sangria.text() == "Sangria: R$ 80,00"
    dlg.fechar()
    assert dlg.result() == 1
    assert "CX-20260923-1000" in perguntas[0]
    assert dlg.fechamento.sangria == Decimal("80.00")
    with transacao(fabrica) as s:
        assert sessao_aberta(s, operador) is None
        assert sugestao_fundo(s, operador) == Decimal("50.00")


def test_fechamento_desistido_nao_fecha(qtbot, fabrica, relogio):
    _, operador, *_ = _loja(fabrica)
    dlg = DialogoFechamento(fabrica, operador, perguntar=lambda _t: False)
    qtbot.addWidget(dlg)
    dlg.fechar()
    assert dlg.result() == 0
    with transacao(fabrica) as s:
        assert sessao_aberta(s, operador) is not None


def test_vendas_da_sessao_operador_cancela_com_autorizacao(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_vendas)
    admin, operador, produto_id, servico_id = _loja(fabrica)
    _vender(fabrica, operador, produto_id=produto_id)
    relogio.avancar(minutes=5)
    _vender(fabrica, operador, servico_id=servico_id, forma=FormaPagamento.PIX)
    pedidos = []
    dlg = DialogoVendasSessao(
        fabrica,
        operador,
        autorizar=_autorizar_como_admin(fabrica, pedidos),
        pedir_motivo=lambda: "Cliente desistiu",
    )
    qtbot.addWidget(dlg)
    assert dlg.tabela.rowCount() == 2
    assert dlg.tabela.item(0, 3).text() == "Troca de óleo"  # mais recente primeiro
    dlg.tabela.setCurrentCell(1, 0)
    dlg.cancelar_selecionada()
    assert "venda nº 1" in pedidos[0]
    assert dlg.tabela.item(1, 7).text() == "Cancelada"
    assert _estoque(fabrica, admin) == Decimal("10")
    dlg.tabela.setCurrentCell(1, 0)
    dlg.cancelar_selecionada()
    assert erros == ["Esta venda já está cancelada."]
    assert len(pedidos) == 1


def test_cancelamento_desistido_nao_cancela_e_admin_nao_precisa_autorizar(qtbot, fabrica, relogio):
    admin, operador, produto_id, _ = _loja(fabrica)
    _vender(fabrica, operador, produto_id=produto_id)
    dlg = DialogoVendasSessao(
        fabrica, operador, autorizar=lambda _t: None, pedir_motivo=lambda: "Erro"
    )
    qtbot.addWidget(dlg)
    dlg.tabela.setCurrentCell(0, 0)
    dlg.cancelar_selecionada()
    assert dlg.tabela.item(0, 7).text() == "Ativa"
    dlg = DialogoVendasSessao(fabrica, admin, autorizar=_nao_autorizar, pedir_motivo=lambda: None)
    qtbot.addWidget(dlg)
    dlg.tabela.setCurrentCell(0, 0)
    dlg.cancelar_selecionada()
    assert dlg.tabela.item(0, 7).text() == "Ativa"
    dlg = DialogoVendasSessao(
        fabrica, admin, autorizar=_nao_autorizar, pedir_motivo=lambda: "Erro de digitação"
    )
    qtbot.addWidget(dlg)
    dlg.tabela.setCurrentCell(0, 0)
    dlg.cancelar_selecionada()
    assert dlg.tabela.item(0, 7).text() == "Cancelada"


def test_botoes_da_tela_pdv_abrem_dialogos_e_fechar_encerra(qtbot, fabrica, relogio, monkeypatch):
    admin, operador, *_ = _loja(fabrica)
    with transacao(fabrica) as s:
        cid = criar_cliente_teste(s, admin)

    class _RecebimentoFeito:
        def __init__(self, _fabrica, ator, _parent=None, **_kwargs):
            self._ator = ator

        def exec(self):
            with transacao(fabrica) as s:
                registrar_recebimento(s, self._ator, cid, Decimal("20"), FormaPagamento.DINHEIRO)
            return 1

    class _FechamentoAceito:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return 1

    monkeypatch.setattr(modulo_pdv, "DialogoRecebimento", _RecebimentoFeito)
    monkeypatch.setattr(modulo_pdv, "DialogoFechamento", _FechamentoAceito)
    tela = TelaPdv(fabrica, operador, perguntar=_nao_perguntar, autorizar=_nao_autorizar)
    qtbot.addWidget(tela)
    assert [b.text() for b in (tela.botao_receber, tela.botao_vendas, tela.botao_fechar)] == [
        "Receber crediário",
        "Vendas da sessão",
        "Fechar caixa",
    ]
    tela.botao_receber.click()
    assert tela.mensagem.text() == "Recebimento registrado."
    assert tela.cabecalho.text().endswith("gaveta R$ 120,00")
    with qtbot.waitSignal(tela.sessao_encerrada, timeout=1000):
        tela.botao_fechar.click()


# --- Além do brief: Enter, foco, busca de cliente, prévia e erros -------------------------


def test_enter_na_busca_de_cliente_nao_salva_o_recebimento(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_recebimento)
    admin, operador, *_ = _loja(fabrica)
    with transacao(fabrica) as s:
        criar_cliente_teste(s, admin)
    dlg = DialogoRecebimento(fabrica, operador, perguntar=_nao_perguntar)
    qtbot.addWidget(dlg)
    dlg.show()
    dlg._busca.campo.setText("ana")
    qtbot.keyClick(dlg._busca.campo, Qt.Key.Key_Return)
    assert "Ana Souza" in dlg._info.text()
    assert erros == []
    assert dlg.isVisible()


def test_enter_na_tabela_de_vendas_nao_abre_o_cancelamento(qtbot, fabrica, relogio):
    _, operador, produto_id, _ = _loja(fabrica)
    _vender(fabrica, operador, produto_id=produto_id)

    def nao_pedir_motivo():
        pytest.fail("Enter na tabela não pode iniciar o cancelamento")

    dlg = DialogoVendasSessao(
        fabrica, operador, autorizar=_nao_autorizar, pedir_motivo=nao_pedir_motivo
    )
    qtbot.addWidget(dlg)
    dlg.show()
    dlg.tabela.setCurrentCell(0, 0)
    qtbot.keyClick(dlg.tabela, Qt.Key.Key_Return)
    assert dlg.tabela.item(0, 7).text() == "Ativa"


def test_enter_no_valor_salva_o_recebimento(qtbot, fabrica, relogio):
    admin, operador, *_ = _loja(fabrica)
    with transacao(fabrica) as s:
        cid = criar_cliente_teste(s, admin)
        lancar_manual(
            s, admin, cid, TipoLancamento.DEBITO, Decimal("100"), MotivoLancamento.COMPRA_ANOTADA
        )
    dlg = DialogoRecebimento(fabrica, operador, perguntar=_nao_perguntar)
    qtbot.addWidget(dlg)
    dlg.show()
    dlg.definir_cliente(cid)
    dlg.valor.setText("30")
    qtbot.keyClick(dlg.valor, Qt.Key.Key_Return)
    assert dlg.result() == 1
    assert _saldo(fabrica, admin, cid) == Decimal("70.00")


def test_foco_inicial_no_primeiro_campo(qtbot, fabrica, relogio):
    _, operador, *_ = _loja(fabrica)
    recebimento = DialogoRecebimento(fabrica, operador, perguntar=_nao_perguntar)
    qtbot.addWidget(recebimento)
    recebimento.show()
    assert recebimento.focusWidget() is recebimento._busca.campo
    fechamento = DialogoFechamento(fabrica, operador, perguntar=_nao_perguntar)
    qtbot.addWidget(fechamento)
    fechamento.show()
    assert fechamento.focusWidget() is fechamento.valor_mantido


def test_busca_de_cliente_compartilhada(qtbot, fabrica, relogio):
    admin, operador, *_ = _loja(fabrica)
    with transacao(fabrica) as s:
        ana = criar_cliente_teste(s, admin, "Ana Souza", celular="11987654321")
        lima = criar_cliente_teste(s, admin, "Ana Lima", celular="21912345678")
    escolhidos: list[int] = []
    avisos: list[str] = []
    busca = BuscaCliente(
        fabrica, operador, "Cliente", ao_escolher=escolhidos.append, ao_avisar=avisos.append
    )
    qtbot.addWidget(busca.campo)
    qtbot.addWidget(busca.opcoes)

    busca.campo.setText("zzz")
    busca.campo.returnPressed.emit()
    assert avisos == ["Nenhum cliente encontrado."]
    assert busca.opcoes.isHidden()

    busca.campo.setText("ana")
    busca.campo.returnPressed.emit()  # dois resultados: escolhe no combo
    assert escolhidos == []
    assert not busca.opcoes.isHidden()
    assert [busca.opcoes.itemData(i) for i in range(busca.opcoes.count())] == [lima, ana]
    busca.opcoes.activated.emit(1)
    assert escolhidos == [ana]
    assert busca.opcoes.isHidden()
    assert busca.campo.text() == ""

    busca.campo.setText("souza")
    busca.campo.returnPressed.emit()  # um só resultado: escolhido direto
    assert escolhidos == [ana, ana]
    assert busca.campo.text() == ""

    busca.campo.setText("ana")
    busca.campo.returnPressed.emit()
    busca.limpar()
    assert busca.campo.text() == ""
    assert busca.opcoes.isHidden()


def test_recebimento_previa_troco_e_forma(qtbot, fabrica, relogio):
    _, operador, *_ = _loja(fabrica)
    dlg = DialogoRecebimento(fabrica, operador, perguntar=_nao_perguntar)
    qtbot.addWidget(dlg)
    assert dlg._previa.text() == "Total a cobrar: —"
    assert dlg.recebido.isEnabled()  # dinheiro é a forma inicial
    dlg.valor.setText("40")
    assert dlg._previa.text() == "Total a cobrar: R$ 40,00"
    dlg.recebido.setText("50")
    assert dlg._previa.text() == "Total a cobrar: R$ 40,00 · Troco: R$ 10,00"
    dlg.recebido.setText("abc")
    assert dlg._previa.text() == "Total a cobrar: R$ 40,00 · Troco: —"
    dlg.forma.setCurrentIndex(dlg.forma.findData(FormaPagamento.PIX))
    assert not dlg.recebido.isEnabled()
    assert dlg.recebido.text() == ""


def test_cancelamento_sem_motivo_nao_pede_autorizacao(qtbot, fabrica, relogio, monkeypatch):
    erros = _erros(monkeypatch, modulo_vendas)
    _, operador, produto_id, _ = _loja(fabrica)
    _vender(fabrica, operador, produto_id=produto_id)
    dlg = DialogoVendasSessao(
        fabrica, operador, autorizar=_nao_autorizar, pedir_motivo=lambda: "   "
    )
    qtbot.addWidget(dlg)
    dlg.tabela.setCurrentCell(0, 0)
    dlg.cancelar_selecionada()
    assert erros == ["Informe o motivo do cancelamento."]
    assert dlg.tabela.item(0, 7).text() == "Ativa"


def test_fechamento_sem_caixa_aberto_levanta_antes_de_criar_o_dialogo(qtbot, fabrica, relogio):
    _, operador, *_ = _loja(fabrica)
    with transacao(fabrica) as s:
        fechar_sessao(s, operador, Decimal("0"))
    pai = QWidget()
    qtbot.addWidget(pai)
    with pytest.raises(SessaoFechada):
        DialogoFechamento(fabrica, operador, pai)
    assert pai.findChildren(DialogoFechamento) == []


def test_fechar_caixa_ja_fechado_por_outro_login_avisa_e_encerra(
    qtbot, fabrica, relogio, monkeypatch
):
    erros = _erros(monkeypatch, modulo_pdv)
    admin, operador, *_ = _loja(fabrica)
    tela = TelaPdv(fabrica, operador, perguntar=_nao_perguntar, autorizar=_nao_autorizar)
    qtbot.addWidget(tela)
    with transacao(fabrica) as s:
        fechar_sessao(s, admin, Decimal("0"))  # outro login fechou o caixa
    with qtbot.waitSignal(tela.sessao_encerrada, timeout=1000):
        tela.botao_fechar.click()
    assert erros == ["Caixa fechado: não há caixa aberto para fechar."]
    assert tela.findChildren(DialogoFechamento) == []


def test_descrever_resumo_lista_formas_cancelamentos_e_totais():
    zero = Decimal("0.00")
    resumo = ResumoSessao(
        fundo_troco=Decimal("100.00"),
        vendas={
            FormaPagamento.PIX: TotaisForma(
                qtd=2,
                bruto=Decimal("60.00"),
                taxa=Decimal("0.60"),
                liquido=Decimal("59.40"),
                cobrado=Decimal("60.00"),
            )
        },
        recebimentos={},
        canceladas_qtd=1,
        canceladas_bruto=Decimal("30.00"),
        total_vendido=Decimal("60.00"),
        dinheiro=zero,
        gaveta=Decimal("100.00"),
    )
    assert descrever_resumo(resumo).splitlines() == [
        "Vendas:",
        "  PIX: 2 · bruto R$ 60,00 · taxa R$ 0,60 · líquido R$ 59,40",
        "Recebimentos de crediário:",
        "  nenhuma",
        "Canceladas: 1 (R$ 30,00, fora dos totais)",
        "Total vendido: R$ 60,00",
        "Fundo de troco: R$ 100,00",
        "Dinheiro recebido: R$ 0,00",
        "Gaveta: R$ 100,00",
    ]
