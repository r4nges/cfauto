from datetime import date

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cfauto.licenca.formato import PayloadLicenca, assinar
from cfauto.licenca.service import EstadoLicenca, StatusLicenca
from cfauto.ui.licenca import DialogoLicenca
from cfauto.ui.tema import PainelMarca


def test_instalar_licenca_pelo_dialogo(qtbot, fabrica, relogio):
    privada = Ed25519PrivateKey.generate()
    dlg = DialogoLicenca(
        fabrica, EstadoLicenca(StatusLicenca.AUSENTE), publica=privada.public_key()
    )
    qtbot.addWidget(dlg)
    dlg.campo_chave.setPlainText("lixo")
    dlg.instalar()
    assert dlg.rotulo_erro.text() == "Licença inválida."
    chave = assinar(PayloadLicenca("Loja", date(2026, 9, 1), date(2027, 9, 1)), privada)
    dlg.campo_chave.setPlainText(chave)
    dlg.instalar()
    assert dlg.estado.valida
    assert dlg.result() == 1  # QDialog.Accepted


def test_dialogo_de_licenca_tem_painel_de_marca_e_papeis(qtbot, fabrica):
    dlg = DialogoLicenca(fabrica, EstadoLicenca(StatusLicenca.AUSENTE))
    qtbot.addWidget(dlg)
    assert dlg.findChild(PainelMarca) is not None
    assert dlg.rotulo_titulo.text() == "Ativar licença"
    assert dlg.rotulo_erro.property("papel") == "erro"
    assert dlg.rotulo_erro.styleSheet() == ""
