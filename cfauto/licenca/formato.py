"""Chave de licença: base64url(payload_json) + '.' + base64url(assinatura Ed25519)."""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from cfauto.core.errors import LicencaInvalida


@dataclass(frozen=True)
class PayloadLicenca:
    cliente: str
    emitida: date
    expira: date
    maquina: str | None = None


def _b64e(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _b64d(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _corpo(payload: PayloadLicenca) -> bytes:
    dados = {
        "cliente": payload.cliente,
        "emitida": payload.emitida.isoformat(),
        "expira": payload.expira.isoformat(),
        "maquina": payload.maquina,
    }
    return json.dumps(dados, sort_keys=True, separators=(",", ":")).encode("utf-8")


def assinar(payload: PayloadLicenca, privada: Ed25519PrivateKey) -> str:
    corpo = _corpo(payload)
    return f"{_b64e(corpo)}.{_b64e(privada.sign(corpo))}"


def verificar_assinatura(chave: str, publica: Ed25519PublicKey) -> PayloadLicenca:
    try:
        corpo_b64, assinatura_b64 = chave.strip().split(".")
        corpo = _b64d(corpo_b64)
        publica.verify(_b64d(assinatura_b64), corpo)
        dados = json.loads(corpo)
        return PayloadLicenca(
            cliente=str(dados["cliente"]),
            emitida=date.fromisoformat(dados["emitida"]),
            expira=date.fromisoformat(dados["expira"]),
            maquina=dados.get("maquina"),
        )
    except (ValueError, KeyError, TypeError, binascii.Error, InvalidSignature) as erro:
        raise LicencaInvalida("Licença inválida.") from erro


def carregar_publica_hex(hex_: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_))


def publica_para_hex(publica: Ed25519PublicKey) -> str:
    return publica.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    ).hex()
