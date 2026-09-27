from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core.db import transacao
from cfauto.ui.login import DialogoLogin

ACEITO = 1  # QDialog.Accepted; result() devolve int


def _criar_admin(fabrica):
    with transacao(fabrica) as s:
        criar_usuario(s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True))


def test_login_errado_mostra_erro(qtbot, fabrica, relogio):
    _criar_admin(fabrica)
    dlg = DialogoLogin(fabrica)
    qtbot.addWidget(dlg)
    dlg.campo_login.setText("dono")
    dlg.campo_senha.setText("errada")
    dlg.entrar()
    assert dlg.ator is None
    assert dlg.rotulo_erro.text() == "Login ou senha inválidos."
    assert dlg.campo_senha.text() == ""


def test_login_certo(qtbot, fabrica, relogio):
    _criar_admin(fabrica)
    dlg = DialogoLogin(fabrica)
    qtbot.addWidget(dlg)
    dlg.campo_login.setText("dono")
    dlg.campo_senha.setText("segredo1")
    dlg.entrar()
    assert dlg.ator is not None and dlg.ator.login == "dono"
    assert dlg.result() == ACEITO


def test_login_fixo_trava_campo(qtbot, fabrica, relogio):
    _criar_admin(fabrica)
    dlg = DialogoLogin(fabrica, login_fixo="dono")
    qtbot.addWidget(dlg)
    assert dlg.campo_login.text() == "dono"
    assert not dlg.campo_login.isEnabled()


def test_login_vazio_mostra_erro(qtbot, fabrica, relogio):
    dlg = DialogoLogin(fabrica)
    qtbot.addWidget(dlg)
    dlg.campo_login.setText("")
    dlg.campo_senha.setText("qualquer")
    dlg.entrar()
    assert dlg.ator is None
    assert dlg.rotulo_erro.text() == "Login obrigatório."
    assert dlg.campo_senha.text() == ""
