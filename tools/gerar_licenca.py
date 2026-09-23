"""Emissão de licenças do CFAUTO. A chave privada NUNCA entra no repositório.

Uso:
  uv run python tools/gerar_licenca.py gerar-chaves [--saida CAMINHO]
  uv run python tools/gerar_licenca.py emitir --cliente "Loja" --dias 365 [--maquina ID]
  uv run python tools/gerar_licenca.py id-maquina
"""

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cfauto.core import clock
from cfauto.licenca.formato import PayloadLicenca, assinar, publica_para_hex
from cfauto.licenca.maquina import id_maquina

PRIVADA_PADRAO = Path.home() / ".cfauto-licenca" / "privada.pem"


def gerar_par(caminho_privada: Path) -> str:
    if caminho_privada.exists():
        raise FileExistsError(f"{caminho_privada} já existe; não vou sobrescrever.")
    caminho_privada.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    privada = Ed25519PrivateKey.generate()
    pem = privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    try:
        fd = os.open(caminho_privada, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as erro:
        raise FileExistsError(f"{caminho_privada} já existe; não vou sobrescrever.") from erro
    with os.fdopen(fd, "wb") as arquivo:
        arquivo.write(pem)
    return publica_para_hex(privada.public_key())


def _carregar_privada(caminho: Path) -> Ed25519PrivateKey:
    chave = serialization.load_pem_private_key(caminho.read_bytes(), password=None)
    if not isinstance(chave, Ed25519PrivateKey):
        raise ValueError("A chave privada não é Ed25519.")
    return chave


def emitir_chave(
    caminho_privada: Path, cliente: str, expira: date, maquina: str | None = None
) -> str:
    payload = PayloadLicenca(cliente=cliente, emitida=clock.hoje(), expira=expira, maquina=maquina)
    return assinar(payload, _carregar_privada(caminho_privada))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_gerar = sub.add_parser("gerar-chaves")
    p_gerar.add_argument("--saida", type=Path, default=PRIVADA_PADRAO)

    p_emitir = sub.add_parser("emitir")
    p_emitir.add_argument("--privada", type=Path, default=PRIVADA_PADRAO)
    p_emitir.add_argument("--cliente", required=True)
    grupo = p_emitir.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--dias", type=int)
    grupo.add_argument("--expira", type=date.fromisoformat)
    p_emitir.add_argument("--maquina")

    sub.add_parser("id-maquina")

    args = parser.parse_args()
    if args.comando == "gerar-chaves":
        print(gerar_par(args.saida))
    elif args.comando == "emitir":
        expira = args.expira or clock.hoje() + timedelta(days=args.dias)
        print(emitir_chave(args.privada, args.cliente, expira, args.maquina))
    else:
        print(id_maquina())


if __name__ == "__main__":
    main()
