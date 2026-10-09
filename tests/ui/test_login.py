from PySide6.QtWidgets import QDialogButtonBox

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core.db import transacao
from cfauto.ui.login import DialogoLogin
from cfauto.ui.tema import PainelMarca

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


def test_login_tem_painel_de_marca_titulo_e_papel_de_erro(qtbot, fabrica):
    dlg = DialogoLogin(fabrica)
    qtbot.addWidget(dlg)
    assert dlg.findChild(PainelMarca) is not None
    assert dlg.rotulo_titulo.text() == "Entrar"
    assert dlg.rotulo_titulo.property("papel") == "titulo"
    assert dlg.rotulo_erro.property("papel") == "erro"
    assert dlg.rotulo_erro.styleSheet() == ""


def test_login_bloqueado_tem_titulo_proprio(qtbot, fabrica):
    dlg = DialogoLogin(fabrica, login_fixo="dono")
    qtbot.addWidget(dlg)
    assert dlg.rotulo_titulo.text() == "Tela bloqueada"


def test_botao_entrar_e_o_padrao_do_dialogo(qtbot, fabrica):
    dlg = DialogoLogin(fabrica)
    qtbot.addWidget(dlg)
    dlg.show()
    botoes = dlg.findChild(QDialogButtonBox)
    assert botoes.button(QDialogButtonBox.StandardButton.Ok).text() == "Entrar"
    assert botoes.button(QDialogButtonBox.StandardButton.Ok).isDefault()
