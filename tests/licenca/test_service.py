from datetime import date, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cfauto.core.errors import LicencaExpirada, LicencaInvalida
from cfauto.licenca.formato import PayloadLicenca, assinar
from cfauto.licenca.service import StatusLicenca, avaliar, instalar, validar


@pytest.fixture
def privada():
    return Ed25519PrivateKey.generate()


def _chave(privada, expira=date(2026, 12, 31), maquina=None):
    return assinar(PayloadLicenca("Loja X", date(2026, 9, 1), expira, maquina), privada)


def test_ausente(sessao, relogio, privada):
    estado = avaliar(sessao, publica=privada.public_key())
    assert estado.status is StatusLicenca.AUSENTE
    assert not estado.valida


def test_instalar_e_avaliar(sessao, relogio, privada):
    estado = instalar(sessao, _chave(privada), publica=privada.public_key())
    assert estado.valida
    assert estado.dias_restantes == (date(2026, 12, 31) - date(2026, 9, 23)).days
    assert estado.payload.cliente == "Loja X"


def test_instalar_expirada(sessao, relogio, privada):
    with pytest.raises(LicencaExpirada):
        instalar(sessao, _chave(privada, expira=date(2026, 9, 22)), publica=privada.public_key())


def test_validar_nao_grava(sessao, relogio, privada):
    validar(_chave(privada), publica=privada.public_key())
    assert avaliar(sessao, publica=privada.public_key()).status is StatusLicenca.AUSENTE


def test_expira_com_o_tempo(sessao, relogio, privada):
    instalar(sessao, _chave(privada), publica=privada.public_key())
    relogio.definir(datetime(2027, 1, 1, 9, 0))
    estado = avaliar(sessao, publica=privada.public_key())
    assert estado.status is StatusLicenca.EXPIRADA
    assert "31/12/2026" in estado.mensagem


def test_relogio_atrasado_bloqueia(sessao, relogio, privada):
    instalar(sessao, _chave(privada), publica=privada.public_key())
    relogio.avancar(days=10)
    assert avaliar(sessao, publica=privada.public_key()).valida
    relogio.avancar(days=-1)
    assert avaliar(sessao, publica=privada.public_key()).valida  # tolerância de 1 dia
    relogio.avancar(days=-2)
    assert avaliar(sessao, publica=privada.public_key()).status is StatusLicenca.RELOGIO


def test_relogio_atrasado_nao_rebaixa_ultima_data(sessao, relogio, privada):
    instalar(sessao, _chave(privada), publica=privada.public_key())
    relogio.avancar(days=10)
    avaliar(sessao, publica=privada.public_key())
    relogio.avancar(days=-5)
    avaliar(sessao, publica=privada.public_key())
    relogio.avancar(days=5)
    assert avaliar(sessao, publica=privada.public_key()).valida


def test_maquina(sessao, relogio, privada):
    chave = _chave(privada, maquina="aaaa")
    with pytest.raises(LicencaInvalida, match="outra máquina"):
        instalar(sessao, chave, publica=privada.public_key(), maquina_atual="bbbb")
    estado = instalar(sessao, chave, publica=privada.public_key(), maquina_atual="aaaa")
    assert estado.valida
    estado = avaliar(sessao, publica=privada.public_key(), maquina_atual="bbbb")
    assert estado.status is StatusLicenca.INVALIDA


def test_chave_invalida_instalada_vira_invalida(sessao, relogio, privada):
    instalar(sessao, _chave(privada), publica=privada.public_key())
    outra = Ed25519PrivateKey.generate()
    estado = avaliar(sessao, publica=outra.public_key())
    assert estado.status is StatusLicenca.INVALIDA


def test_dias_restantes_no_ultimo_dia(sessao, relogio, privada):
    instalar(sessao, _chave(privada, expira=date(2026, 9, 23)), publica=privada.public_key())
    assert avaliar(sessao, publica=privada.public_key()).dias_restantes == 0
    relogio.avancar(days=1)
    assert not avaliar(sessao, publica=privada.public_key()).valida
