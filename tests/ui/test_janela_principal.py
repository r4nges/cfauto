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
    ator = Ator(2, "Maria", "maria", False, frozenset({Modulo.CLIENTES, Modulo.PDV}))
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    assert janela.titulos_navegacao() == ["PDV / Caixa", "Clientes"]


def test_admin_ve_tudo(qtbot, fabrica):
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
        "CFAUTO",
        "Usuários",
        "Auditoria",
    ]


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
