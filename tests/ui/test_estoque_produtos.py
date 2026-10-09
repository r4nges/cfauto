from datetime import date
from decimal import Decimal

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core.db import transacao
from cfauto.core.permissoes import Ator, Modulo
from cfauto.estoque.models import Destino, MotivoAjuste
from cfauto.estoque.produtos import buscar_produtos, criar_produto
from cfauto.estoque.schemas import DadosProduto
from cfauto.licenca.formato import PayloadLicenca
from cfauto.licenca.service import EstadoLicenca, StatusLicenca
from cfauto.ui.estoque import produtos as tela_produtos
from cfauto.ui.estoque.pagina import PaginaEstoque
from cfauto.ui.estoque.produtos import DialogoAjusteEstoque, DialogoProduto, TelaProdutos
from cfauto.ui.janela_principal import JanelaPrincipal


def _admin(fabrica):
    with transacao(fabrica) as s:
        return criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )


def _criar(fabrica, ator, descricao, **campos):
    with transacao(fabrica) as s:
        return criar_produto(s, ator, DadosProduto(descricao=descricao, **campos))


def test_pagina_estoque_comeca_pela_aba_produtos(qtbot, fabrica, relogio):
    pagina = PaginaEstoque(fabrica, _admin(fabrica))
    qtbot.addWidget(pagina)
    assert pagina.titulos()[0] == "Produtos"


def test_dialogo_cria_produto_com_valores_brasileiros(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    dlg = DialogoProduto(fabrica, ator)
    qtbot.addWidget(dlg)
    dlg.descricao.setText("Café Pilão 500g")
    dlg.fator.setText("1")
    dlg.preco_entrada.setText("0,035")
    dlg.preco_venda.setText("1.234,50")
    dlg.estoque_inicial.setText("2,5")
    dlg.salvar()
    assert dlg.result() == 1
    tela = TelaProdutos(fabrica, ator)
    qtbot.addWidget(tela)
    assert tela.codigos_na_tabela() == ["0001"]
    assert tela.tabela.item(0, 5).text() == "2,5"
    assert tela.tabela.item(0, 7).text() == "R$ 1.234,50"
    with transacao(fabrica) as s:
        assert buscar_produtos(s, ator)[0].preco_entrada == Decimal("0.0350")


def test_valor_invalido_mostra_erro_e_nao_fecha(qtbot, fabrica, relogio, monkeypatch):
    erros = []
    monkeypatch.setattr(tela_produtos, "mostrar_erro", lambda _pai, erro: erros.append(str(erro)))
    dlg = DialogoProduto(fabrica, _admin(fabrica))
    qtbot.addWidget(dlg)
    dlg.descricao.setText("Produto")
    dlg.preco_venda.setText("abc")
    dlg.salvar()
    assert dlg.result() == 0
    assert erros[0].startswith("Preço de venda")


def test_custo_unitario_e_margem_ao_vivo(qtbot, fabrica, relogio):
    dlg = DialogoProduto(fabrica, _admin(fabrica))
    qtbot.addWidget(dlg)
    dlg.fator.setText("12")
    dlg.preco_entrada.setText("24,00")
    dlg.preco_venda.setText("4,00")
    assert dlg.fracionado_rotulo.text() == "R$ 2,00"
    assert dlg.margem_rotulo.text() == "50,0%"
    dlg.fator.setText("0")
    assert dlg.margem_rotulo.text() == "—"


def _dialogo_com_custo(qtbot, fabrica, fator="12", entrada="24,00"):
    dlg = DialogoProduto(fabrica, _admin(fabrica))
    qtbot.addWidget(dlg)
    dlg.fator.setText(fator)
    dlg.preco_entrada.setText(entrada)
    return dlg  # custo por unidade: R$ 2,00


def test_markup_digitado_calcula_o_preco_de_venda(qtbot, fabrica, relogio):
    dlg = _dialogo_com_custo(qtbot, fabrica)
    qtbot.keyClicks(dlg.markup, "50")
    assert dlg.markup.text() == "50"  # não reescreve o que a pessoa está digitando
    assert dlg.preco_venda.text() == "3,00"
    assert dlg.margem_rotulo.text() == "33,3%"
    qtbot.keyClicks(dlg.markup, ",5")
    assert dlg.preco_venda.text() == "3,01"  # 2 × 1,505 = 3,01


def test_preco_digitado_calcula_o_markup(qtbot, fabrica, relogio):
    dlg = _dialogo_com_custo(qtbot, fabrica)
    dlg.preco_venda.clear()
    qtbot.keyClicks(dlg.preco_venda, "3,00")
    assert dlg.markup.text() == "50,00"
    dlg.preco_venda.setText("1,00")
    assert dlg.markup.text() == "-50,00"


def test_mudar_o_custo_mantem_o_preco_e_recalcula_o_markup(qtbot, fabrica, relogio):
    dlg = _dialogo_com_custo(qtbot, fabrica)
    dlg.preco_venda.setText("3,00")
    assert dlg.markup.text() == "50,00"
    dlg.preco_entrada.setText("30,00")  # custo por unidade: R$ 2,50
    assert dlg.preco_venda.text() == "3,00"
    assert dlg.markup.text() == "20,00"


def test_markup_sem_custo_fica_desabilitado(qtbot, fabrica, relogio):
    dlg = DialogoProduto(fabrica, _admin(fabrica))
    qtbot.addWidget(dlg)
    assert not dlg.markup.isEnabled()
    assert dlg.markup.text() == "—"
    dlg.preco_entrada.setText("24,00")
    assert dlg.markup.isEnabled()
    assert dlg.markup.text() == ""  # custo conhecido, preço ainda não: espera o markup
    dlg.fator.setText("0")
    assert not dlg.markup.isEnabled()
    assert dlg.markup.text() == "—"


def test_markup_digitado_vai_para_o_preco_salvo(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    dlg = DialogoProduto(fabrica, ator)
    qtbot.addWidget(dlg)
    dlg.descricao.setText("Café")
    dlg.preco_entrada.setText("10,00")
    qtbot.keyClicks(dlg.markup, "40")
    dlg.salvar()
    assert dlg.result() == 1
    with transacao(fabrica) as s:
        assert buscar_produtos(s, ator)[0].preco_venda == Decimal("14.00")


def test_editar_mostra_o_markup_do_preco_cadastrado(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    produto = _criar(fabrica, ator, "Arroz", preco_entrada=Decimal("20"), preco_venda=Decimal("30"))
    dlg = DialogoProduto(fabrica, ator, produto)
    qtbot.addWidget(dlg)
    assert dlg.markup.text() == "50,00"


def test_editar_carrega_dados_e_marca_minimo_manual(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    produto = _criar(
        fabrica, ator, "Arroz", preco_entrada=Decimal("20"), destino=Destino.USO_CONSUMO
    )
    dlg = DialogoProduto(fabrica, ator, produto)
    qtbot.addWidget(dlg)
    assert dlg.preco_entrada.text() == "20,00"
    assert dlg.destino.currentText() == "Uso/Consumo"
    assert not dlg.minimo_manual.isChecked()
    qtbot.keyClicks(dlg.estoque_minimo, "5")
    assert dlg.minimo_manual.isChecked()


def test_busca_filtra_a_tabela(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    _criar(fabrica, ator, "Café Pilão")
    _criar(fabrica, ator, "Açúcar")
    tela = TelaProdutos(fabrica, ator)
    qtbot.addWidget(tela)
    assert tela.codigos_na_tabela() == ["0002", "0001"]
    tela.busca.setText("cafe")
    assert tela.codigos_na_tabela() == ["0001"]


def test_ajuste_pelo_dialogo(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    produto = _criar(fabrica, ator, "Arroz", estoque_inicial=Decimal("10"))
    dlg = DialogoAjusteEstoque(fabrica, ator, produto)
    qtbot.addWidget(dlg)
    dlg.nova_quantidade.setText("7")
    dlg.motivo.setCurrentIndex(list(MotivoAjuste).index(MotivoAjuste.PERDA_AVARIA))
    dlg.salvar()
    assert dlg.result() == 1
    with transacao(fabrica) as s:
        assert buscar_produtos(s, ator)[0].estoque == Decimal("7")


def test_desativar_pela_tela(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    _criar(fabrica, ator, "Arroz")
    tela = TelaProdutos(fabrica, ator)
    qtbot.addWidget(tela)
    tela.selecionar(0)
    tela.alternar_ativo()
    assert tela.codigos_na_tabela() == []
    tela.mostrar_inativos.setChecked(True)
    tela.selecionar(0)
    assert tela.botao_ativo.text() == "Reativar"


def test_janela_principal_usa_a_pagina_estoque(qtbot, fabrica, relogio):
    ator = Ator(1, "Estoquista", "est", False, frozenset({Modulo.ESTOQUE}))
    estado = EstadoLicenca(
        StatusLicenca.VALIDA, PayloadLicenca("Loja", date(2026, 1, 1), date(2027, 1, 1)), 100
    )
    janela = JanelaPrincipal(fabrica, ator, estado)
    qtbot.addWidget(janela)
    assert janela.titulos_navegacao() == ["Estoque"]
    assert isinstance(janela.pagina_atual(), PaginaEstoque)
