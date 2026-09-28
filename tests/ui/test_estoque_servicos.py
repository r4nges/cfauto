from decimal import Decimal

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core.db import transacao
from cfauto.estoque.schemas import DadosMaterial, DadosServico
from cfauto.estoque.servicos import criar_servico
from cfauto.ui.estoque import servicos as tela_servicos
from cfauto.ui.estoque.pagina import PaginaEstoque
from cfauto.ui.estoque.servicos import DialogoServico, TelaServicos


def _admin(fabrica):
    with transacao(fabrica) as s:
        return criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )


def test_pagina_estoque_tem_aba_servicos(qtbot, fabrica, relogio):
    pagina = PaginaEstoque(fabrica, _admin(fabrica))
    qtbot.addWidget(pagina)
    assert "Serviços" in pagina.titulos()


def test_dialogo_cria_servico_com_preco_ao_vivo(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    dlg = DialogoServico(fabrica, ator)
    qtbot.addWidget(dlg)
    dlg.nome.setText("Troca de tomada")
    dlg.materiais.item(0, 0).setText("Tomada")
    dlg.materiais.item(0, 1).setText("2,50")
    dlg.materiais.item(0, 2).setText("2")
    dlg.adicionar_material("Fita isolante", "1,00", "1")
    assert dlg.preco_rotulo.text() == "R$ 9,00"
    dlg.salvar()
    assert dlg.result() == 1
    tela = TelaServicos(fabrica, ator)
    qtbot.addWidget(tela)
    assert tela.codigos_na_tabela() == ["SERV-001"]
    assert tela.tabela.item(0, 5).text() == "R$ 9,00"


def test_editar_servico_carrega_materiais(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    with transacao(fabrica) as s:
        criar_servico(
            s,
            ator,
            DadosServico(
                nome="Instalação",
                materiais=(DadosMaterial("Cabo", Decimal("10"), Decimal("3")),),
                mao_obra_pct=Decimal("20"),
            ),
        )
    tela = TelaServicos(fabrica, ator)
    qtbot.addWidget(tela)
    dlg = DialogoServico(fabrica, ator, tela.servico_da_linha(0))
    qtbot.addWidget(dlg)
    assert dlg.materiais.rowCount() == 1
    assert (dlg.materiais.item(0, 1).text(), dlg.materiais.item(0, 2).text()) == ("10,00", "3")
    assert dlg.mao_obra.text() == "20"
    assert dlg.preco_rotulo.text() == "R$ 36,00"
    dlg.materiais.item(0, 2).setText("4")
    assert dlg.preco_rotulo.text() == "R$ 48,00"
    dlg.salvar()
    tela.recarregar()
    assert tela.tabela.item(0, 5).text() == "R$ 48,00"


def test_sem_materiais_mostra_erro(qtbot, fabrica, relogio, monkeypatch):
    erros = []
    monkeypatch.setattr(tela_servicos, "mostrar_erro", lambda _pai, erro: erros.append(str(erro)))
    dlg = DialogoServico(fabrica, _admin(fabrica))
    qtbot.addWidget(dlg)
    dlg.nome.setText("Vazio")
    dlg.salvar()
    assert dlg.result() == 0
    assert "material" in erros[0]


def test_desativar_servico_pela_tela(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    with transacao(fabrica) as s:
        criar_servico(
            s, ator, DadosServico(nome="X", materiais=(DadosMaterial("Fio", Decimal("1")),))
        )
    tela = TelaServicos(fabrica, ator)
    qtbot.addWidget(tela)
    tela.selecionar(0)
    tela.alternar_ativo()
    assert tela.codigos_na_tabela() == []
