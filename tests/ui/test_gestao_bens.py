from decimal import Decimal

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core.db import transacao
from cfauto.gestao.bens import criar_bem
from cfauto.gestao.models import TipoBem
from cfauto.gestao.schemas import DadosBem
from cfauto.ui.configuracoes import PaginaConfiguracoes
from cfauto.ui.gestao import bens as tela_bens
from cfauto.ui.gestao.bens import DialogoBem, TelaBens
from cfauto.ui.gestao.pagina import PaginaGestao


def _admin(fabrica):
    with transacao(fabrica) as s:
        return criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )


def test_dialogo_cria_bem_e_tela_mostra_total(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    dlg = DialogoBem(fabrica, ator)
    qtbot.addWidget(dlg)
    assert dlg.data.date().toString("dd/MM/yyyy") == "23/09/2026"
    dlg.descricao.setText("Balcão refrigerado")
    dlg.valor.setText("3.500,00")
    dlg.salvar()
    assert dlg.result() == 1
    tela = TelaBens(fabrica, ator)
    qtbot.addWidget(tela)
    assert tela.codigos_na_tabela() == ["BEM-001"]
    assert tela.tabela.item(0, 3).text() == "R$ 3.500,00"
    assert tela.tabela.item(0, 4).text() == "23/09/2026"
    assert tela.total_rotulo.text() == "Total dos bens ativos: R$ 3.500,00"


def test_baixar_tira_do_total(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    with transacao(fabrica) as s:
        criar_bem(s, ator, DadosBem(descricao="Freezer", tipo=TipoBem.MOVEL, valor=Decimal("2000")))
    tela = TelaBens(fabrica, ator)
    qtbot.addWidget(tela)
    tela.selecionar(0)
    tela.alternar_situacao()
    assert tela.codigos_na_tabela() == []
    assert tela.total_rotulo.text().endswith("R$ 0,00")
    tela.mostrar_baixados.setChecked(True)
    assert tela.tabela.item(0, 5).text() == "Baixado"


def test_valor_em_branco_mostra_erro(qtbot, fabrica, relogio, monkeypatch):
    erros = []
    monkeypatch.setattr(tela_bens, "mostrar_erro", lambda _pai, erro: erros.append(str(erro)))
    dlg = DialogoBem(fabrica, _admin(fabrica))
    qtbot.addWidget(dlg)
    dlg.descricao.setText("Mesa")
    dlg.salvar()
    assert dlg.result() == 0
    assert erros[0].startswith("Valor")


def test_configuracoes_mostra_bens_fisicos_na_aba_cfauto(qtbot, fabrica, relogio):
    pagina = PaginaConfiguracoes(fabrica, _admin(fabrica))
    qtbot.addWidget(pagina)
    gestao = pagina.widget(0)
    assert isinstance(gestao, PaginaGestao)
    assert gestao.titulos() == ["Bens Físicos"]
