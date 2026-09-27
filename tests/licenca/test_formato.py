from dataclasses import replace
from datetime import date

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cfauto.core.errors import LicencaInvalida
from cfauto.licenca.chave_publica import CHAVE_PUBLICA_HEX
from cfauto.licenca.formato import (
    PayloadLicenca,
    assinar,
    carregar_publica_hex,
    publica_para_hex,
    verificar_assinatura,
)

PAYLOAD = PayloadLicenca("Loja X", date(2026, 9, 23), date(2027, 9, 23), None)


def test_ida_e_volta():
    privada = Ed25519PrivateKey.generate()
    chave = assinar(PAYLOAD, privada)
    assert verificar_assinatura(chave, privada.public_key()) == PAYLOAD


def test_outra_chave_publica_rejeita():
    chave = assinar(PAYLOAD, Ed25519PrivateKey.generate())
    with pytest.raises(LicencaInvalida):
        verificar_assinatura(chave, Ed25519PrivateKey.generate().public_key())


def test_payload_adulterado_rejeita():
    privada = Ed25519PrivateKey.generate()
    _, assinatura = assinar(PAYLOAD, privada).split(".")
    corpo_falso, _ = assinar(replace(PAYLOAD, expira=date(2099, 1, 1)), privada).split(".")
    with pytest.raises(LicencaInvalida):
        verificar_assinatura(f"{corpo_falso}.{assinatura}", privada.public_key())


@pytest.mark.parametrize("lixo", ["", "abc", "a.b.c", "!!!.???"])
def test_lixo_rejeita(lixo):
    with pytest.raises(LicencaInvalida):
        verificar_assinatura(lixo, Ed25519PrivateKey.generate().public_key())


def test_hex_publica():
    publica = Ed25519PrivateKey.generate().public_key()
    assert publica_para_hex(carregar_publica_hex(publica_para_hex(publica))) == publica_para_hex(
        publica
    )


def test_chave_publica_embutida_valida():
    assert len(CHAVE_PUBLICA_HEX) == 64
    carregar_publica_hex(CHAVE_PUBLICA_HEX)
