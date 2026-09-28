from datetime import date

import pytest

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.clientes.cadastro import criar_cliente, obter_cliente
from cfauto.clientes.schemas import DadosCliente, DadosDependente
from cfauto.core.db import transacao
from cfauto.core.permissoes import Modulo
from cfauto.licenca.formato import PayloadLicenca
from cfauto.licenca.service import EstadoLicenca, StatusLicenca
from cfauto.ui.clientes import dialogo_cliente as modulo_dialogo
from cfauto.ui.clientes import tela as modulo_tela
from cfauto.ui.clientes.dialogo_cliente import DialogoCliente
from cfauto.ui.clientes.tela import TelaClientes
from cfauto.ui.janela_principal import JanelaPrincipal


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
                modulos=frozenset({Modulo.CLIENTES}),
            ),
        )
    return admin, operador


def _criar(fabrica, ator, nome="Ana Souza", celular="11987654321", **campos):
    with transacao(fabrica) as s:
        return criar_cliente(s, ator, DadosCliente(nome=nome, celular=celular, **campos))


def _nao_perguntar(texto):
    pytest.fail(f"não deveria perguntar: {texto}")


def test_dialogo_cria_cliente_e_tela_lista(qtbot, fabrica, relogio):
    admin, _ = _atores(fabrica)
    dlg = DialogoCliente(fabrica, admin)
    qtbot.addWidget(dlg)
    assert dlg.limite.text() == "500,00"
    dlg.nome.setText("Ana Souza")
    dlg.celular.setText("11987654321")
    dlg.cpf.setText("52998224725")
    dlg.nascimento.setText("01/05/1990")
    dlg.dependentes_nome[0].setText("João Souza")
    dlg.dependentes_parentesco[0].setText("filho")
    dlg.salvar(confirmar=_nao_perguntar)
    assert dlg.result() == 1
    tela = TelaClientes(fabrica, admin)
    qtbot.addWidget(tela)
    assert tela.codigos_na_tabela() == ["CLI-0001"]
    assert [tela.tabela.item(0, j).text() for j in range(6)] == [
        "CLI-0001",
        "Ana Souza",
        "(11) 98765-4321",
        "R$ 0,00",
        "R$ 500,00",
        "Ativo",
    ]
    with transacao(fabrica) as s:
        ficha = obter_cliente(s, admin, dlg.cliente_id)
    assert ficha.dados.nascimento == date(1990, 5, 1)
    assert ficha.dados.dependentes == (DadosDependente("João Souza", "filho"),)


def test_celular_e_cpf_sao_formatados_ao_sair_do_campo(qtbot, fabrica, relogio):
    admin, _ = _atores(fabrica)
    dlg = DialogoCliente(fabrica, admin)
    qtbot.addWidget(dlg)
    dlg.celular.setText("+55 11 98765 4321")
    dlg.celular.editingFinished.emit()
    dlg.cpf.setText("52998224725")
    dlg.cpf.editingFinished.emit()
    assert (dlg.celular.text(), dlg.cpf.text()) == ("(11) 98765-4321", "529.982.247-25")
    dlg.celular.setText("123")
    dlg.celular.editingFinished.emit()
    assert dlg.celular.text() == "123"  # inválido fica como digitado; o erro vem ao salvar


def test_erro_de_validacao_mostra_erro_e_nao_fecha(qtbot, fabrica, relogio, monkeypatch):
    erros = []
    monkeypatch.setattr(modulo_dialogo, "mostrar_erro", lambda _pai, erro: erros.append(str(erro)))
    admin, _ = _atores(fabrica)
    dlg = DialogoCliente(fabrica, admin)
    qtbot.addWidget(dlg)
    dlg.nome.setText("Ana")
    dlg.celular.setText("11987654321")
    dlg.salvar(confirmar=_nao_perguntar)
    assert dlg.result() == 0
    assert "sobrenome" in erros[0]
    dlg.nome.setText("Ana Souza")
    dlg.nascimento.setText("31/02/1990")
    dlg.salvar(confirmar=_nao_perguntar)
    assert erros[1].startswith("Nascimento")


def test_duplicado_pergunta_e_cancelar_nao_salva(qtbot, fabrica, relogio):
    admin, _ = _atores(fabrica)
    _criar(fabrica, admin)
    dlg = DialogoCliente(fabrica, admin)
    qtbot.addWidget(dlg)
    dlg.nome.setText("Filho Souza")
    dlg.celular.setText("(11) 98765-4321")
    perguntas = []
    dlg.salvar(confirmar=lambda texto: perguntas.append(texto) or False)
    assert dlg.result() == 0
    assert "CLI-0001" in perguntas[0]
    dlg.salvar(confirmar=lambda _texto: True)
    assert dlg.result() == 1
    tela = TelaClientes(fabrica, admin)
    qtbot.addWidget(tela)
    assert tela.codigos_na_tabela() == ["CLI-0001", "CLI-0002"]


def test_somente_titular_limpa_dependentes(qtbot, fabrica, relogio):
    admin, _ = _atores(fabrica)
    dlg = DialogoCliente(fabrica, admin)
    qtbot.addWidget(dlg)
    dlg.dependentes_nome[0].setText("João Souza")
    dlg.somente_titular.setChecked(True)
    assert dlg.dependentes_nome[0].text() == ""
    assert not dlg.dependentes_nome[0].isEnabled()
    dlg.somente_titular.setChecked(False)
    assert dlg.dependentes_nome[0].isEnabled()


def test_sem_limite_desabilita_campo(qtbot, fabrica, relogio):
    admin, _ = _atores(fabrica)
    dlg = DialogoCliente(fabrica, admin)
    qtbot.addWidget(dlg)
    dlg.sem_limite.setChecked(True)
    assert not dlg.limite.isEnabled()
    dlg.nome.setText("Ana Souza")
    dlg.celular.setText("11987654321")
    assert dlg.dados().limite is None


def test_operador_nao_edita_limite_nem_ve_botoes_admin(qtbot, fabrica, relogio):
    _, operador = _atores(fabrica)
    dlg = DialogoCliente(fabrica, operador)
    qtbot.addWidget(dlg)
    assert not dlg.limite.isEnabled()
    assert not dlg.sem_limite.isEnabled()
    tela = TelaClientes(fabrica, operador)
    qtbot.addWidget(tela)
    assert tela.botao_situacao.isHidden()
    assert tela.botao_excluir.isHidden()


def test_operador_edita_cliente_sem_limite_pela_tela(qtbot, fabrica, relogio):
    admin, operador = _atores(fabrica)
    cid = _criar(fabrica, admin, limite=None, cpf="52998224725", nascimento=date(1990, 5, 1))
    with transacao(fabrica) as s:
        ficha = obter_cliente(s, operador, cid)
    dlg = DialogoCliente(fabrica, operador, ficha)
    qtbot.addWidget(dlg)
    assert (dlg.celular.text(), dlg.cpf.text(), dlg.nascimento.text()) == (
        "(11) 98765-4321",
        "529.982.247-25",
        "01/05/1990",
    )
    assert dlg.sem_limite.isChecked()
    dlg.nome.setText("Ana Souza Lima")
    dlg.salvar(confirmar=_nao_perguntar)
    assert dlg.result() == 1
    with transacao(fabrica) as s:
        atualizado = obter_cliente(s, operador, cid)
    assert (atualizado.dados.nome, atualizado.dados.limite) == ("Ana Souza Lima", None)


def test_busca_inativar_e_excluir_pela_tela(qtbot, fabrica, relogio, monkeypatch):
    admin, _ = _atores(fabrica)
    _criar(fabrica, admin)
    _criar(fabrica, admin, nome="Bia Lima", celular="21912345678")
    tela = TelaClientes(fabrica, admin)
    qtbot.addWidget(tela)
    tela.busca.setText("bia")
    assert tela.codigos_na_tabela() == ["CLI-0002"]
    tela.busca.setText("")
    tela.selecionar(0)
    tela.alternar_situacao()
    assert tela.codigos_na_tabela() == ["CLI-0002"]
    tela.mostrar_inativos.setChecked(True)
    assert tela.tabela.item(0, 5).text() == "Inativo"
    tela.selecionar(0)
    assert tela.botao_situacao.text() == "Reativar"
    perguntas = []
    tela.excluir_selecionado(lambda texto: perguntas.append(texto) or True)
    assert "CLI-0001" in perguntas[0]
    assert tela.codigos_na_tabela() == ["CLI-0002"]


def test_janela_principal_abre_clientes(qtbot, fabrica, relogio):
    admin, _ = _atores(fabrica)
    estado = EstadoLicenca(
        StatusLicenca.VALIDA, PayloadLicenca("Loja", date(2026, 1, 1), date(2027, 1, 1)), 100
    )
    janela = JanelaPrincipal(fabrica, admin, estado)
    qtbot.addWidget(janela)
    janela.selecionar_modulo(janela.titulos_navegacao().index("Clientes"))
    assert isinstance(janela.pagina_atual(), TelaClientes)
    assert modulo_tela.TelaClientes is TelaClientes
