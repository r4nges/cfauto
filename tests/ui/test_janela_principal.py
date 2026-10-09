from datetime import date
from decimal import Decimal

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.caixa.sessao import fechar_sessao
from cfauto.core.db import transacao
from cfauto.core.permissoes import Ator, Modulo
from cfauto.licenca.formato import PayloadLicenca
from cfauto.licenca.service import EstadoLicenca, StatusLicenca
from cfauto.ui.caixa.pagina import PaginaCaixa
from cfauto.ui.clientes.tela import TelaClientes
from cfauto.ui.historico.tela import TelaHistorico
from cfauto.ui.janela_principal import JanelaPrincipal
from cfauto.ui.parametros import PaginaParametros
from tests.fabricas import abrir_caixa


def _estado(dias):
    return EstadoLicenca(
        StatusLicenca.VALIDA, PayloadLicenca("Loja", date(2026, 1, 1), date(2027, 1, 1)), dias
    )


def test_operador_ve_so_seus_modulos(qtbot, fabrica):
    modulos = frozenset({Modulo.CLIENTES, Modulo.PDV, Modulo.CFAUTO, Modulo.USUARIOS})
    ator = Ator(2, "Maria", "maria", False, modulos)
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    assert janela.titulos_navegacao() == ["PDV / Caixa", "Clientes"]
    assert not janela.acao_configuracoes.isVisible()
    assert janela.titulos_configuracoes() == []


def test_admin_ve_modulos_na_navegacao_e_admin_em_configuracoes(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    assert janela.titulos_navegacao() == [
        "PDV / Caixa",
        "Estoque",
        "Clientes",
        "Saídas",
        "Compras",
        "Histórico",
    ]
    assert janela.acao_configuracoes.isVisible()
    assert janela.titulos_configuracoes() == ["CFAUTO", "Usuários", "Auditoria", "Parâmetros"]


def test_configuracoes_troca_pagina_e_volta_pela_navegacao(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    janela.acao_configuracoes.trigger()
    assert janela.pagina_atual() is janela.configuracoes
    janela.selecionar_modulo(0)
    assert janela.pagina_atual() is not janela.configuracoes


def test_botao_de_menu_recolhe_e_mostra_navegacao(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    assert janela.navegacao_visivel()
    janela.acao_menu.trigger()
    assert not janela.navegacao_visivel()
    janela.acao_menu.trigger()
    assert janela.navegacao_visivel()


def test_logo_ocupa_a_barra_lateral_e_some_com_o_menu(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    janela.show()
    assert janela.logo.renderer().isValid()
    assert janela.logo.isVisible()
    janela.acao_menu.trigger()
    assert not janela.logo.isVisible()
    janela.acao_menu.trigger()
    assert janela.logo.isVisible()


def test_aviso_de_licenca_perto_do_fim(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(10))
    qtbot.addWidget(janela)
    assert "10 dias" in janela.aviso_licenca.text()
    longe = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(longe)
    assert longe.aviso_licenca.text() == ""


def test_sair_emite_sinal_sem_encerrar(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    encerrou = []
    janela.encerrar.connect(lambda: encerrou.append(True))
    with qtbot.waitSignal(janela.sair, timeout=1000):
        janela.acao_sair.trigger()
    assert encerrou == []


def test_fechar_sessao_nao_emite_encerrar(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    encerrou = []
    janela.encerrar.connect(lambda: encerrou.append(True))
    janela.fechar_sessao()
    assert encerrou == []


def test_fechar_pelo_x_emite_encerrar(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    encerrou = []
    janela.encerrar.connect(lambda: encerrou.append(True))
    janela.close()
    assert encerrou == [True]


def test_admin_tem_pdv_historico_e_parametros_de_verdade(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    janela.selecionar_modulo(0)
    assert isinstance(janela.pagina_atual(), PaginaCaixa)
    janela.selecionar_modulo(5)
    assert isinstance(janela.pagina_atual(), TelaHistorico)
    assert janela.configuracoes is not None
    assert isinstance(janela.configuracoes.widget(3), PaginaParametros)


def test_usuario_sem_o_modulo_nao_ganha_a_pagina_nem_o_erro_de_permissao(qtbot, fabrica):
    ator = Ator(2, "Maria", "maria", False, frozenset({Modulo.CLIENTES}))
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    assert janela.titulos_navegacao() == ["Clientes"]
    assert janela.configuracoes is None
    assert isinstance(janela.pagina_atual(), TelaClientes)


def test_historico_e_pdv_recarregam_ao_navegar_ate_eles(qtbot, fabrica, relogio):
    with transacao(fabrica) as s:
        admin = criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )
    janela = JanelaPrincipal(fabrica, admin, _estado(100))
    qtbot.addWidget(janela)
    janela.selecionar_modulo(5)
    historico = janela.pagina_atual()
    assert isinstance(historico, TelaHistorico)
    assert historico.sessoes.rowCount() == 0
    janela.selecionar_modulo(0)
    caixa = janela.pagina_atual()
    assert isinstance(caixa, PaginaCaixa)
    assert caixa.currentWidget() is caixa.fechado
    with transacao(fabrica) as s:
        abrir_caixa(s, admin)
        fechar_sessao(s, admin, Decimal("0"))
        abrir_caixa(s, admin)
    janela.selecionar_modulo(5)
    assert historico.sessoes.rowCount() == 1
    janela.selecionar_modulo(0)
    assert caixa.currentWidget() is caixa.pdv
