from datetime import date

from cfauto.core.permissoes import Ator, Modulo
from cfauto.licenca.formato import PayloadLicenca
from cfauto.licenca.service import EstadoLicenca, StatusLicenca
from cfauto.ui.janela_principal import JanelaPrincipal


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
