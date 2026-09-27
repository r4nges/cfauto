from cfauto.auth.service import NovoUsuario, autenticar, criar_usuario
from cfauto.core.db import transacao
from cfauto.core.permissoes import Modulo
from cfauto.ui.usuarios import DialogoUsuario, TelaUsuarios


def _admin(fabrica):
    with transacao(fabrica) as s:
        return criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )


def test_tela_lista_usuarios(qtbot, fabrica, relogio):
    admin = _admin(fabrica)
    tela = TelaUsuarios(fabrica, admin)
    qtbot.addWidget(tela)
    assert tela.ids_na_tabela() == [admin.id]
    assert tela.tabela.item(0, 1).text() == "dono"


def test_dialogo_cria_usuario(qtbot, fabrica, relogio):
    admin = _admin(fabrica)
    dlg = DialogoUsuario(fabrica, admin)
    qtbot.addWidget(dlg)
    dlg.nome.setText("Maria")
    dlg.login.setText("maria")
    dlg.senha.setText("segredo2")
    dlg.caixas_modulo[Modulo.PDV].setChecked(True)
    dlg.salvar()
    assert dlg.result() == 1  # QDialog.Accepted
    with transacao(fabrica) as s:
        ator = autenticar(s, "maria", "segredo2")
    assert ator.modulos == frozenset({Modulo.PDV})


def test_dialogo_edita_usuario(qtbot, fabrica, relogio):
    admin = _admin(fabrica)
    tela = TelaUsuarios(fabrica, admin)
    qtbot.addWidget(tela)
    with transacao(fabrica) as s:
        criar_usuario(s, admin, NovoUsuario(nome="Maria", login="maria", senha="segredo2"))
    tela.recarregar()
    usuario = tela.usuario_da_linha(1)
    dlg = DialogoUsuario(fabrica, admin, usuario)
    qtbot.addWidget(dlg)
    assert not dlg.login.isEnabled()
    dlg.caixas_modulo[Modulo.ESTOQUE].setChecked(True)
    dlg.salvar()
    with transacao(fabrica) as s:
        assert autenticar(s, "maria", "segredo2").modulos == frozenset({Modulo.ESTOQUE})


def test_dialogo_nao_oferece_modulos_so_admin(qtbot, fabrica, relogio):
    dlg = DialogoUsuario(fabrica, _admin(fabrica))
    qtbot.addWidget(dlg)
    assert Modulo.CFAUTO not in dlg.caixas_modulo
    assert Modulo.USUARIOS not in dlg.caixas_modulo
