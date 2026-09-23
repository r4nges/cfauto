import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def verificar(hash_: str, senha: str) -> bool:
    try:
        return _hasher.verify(hash_, senha)
    except (VerificationError, InvalidHashError):
        return False


def precisa_rehash(hash_: str) -> bool:
    return _hasher.check_needs_rehash(hash_)


def verificar_legado(hash_hex: str, senha: str) -> bool:
    """SHA-256 hex sem sal, usado pela planilha USUÁRIOS do sistema original."""
    calculado = hashlib.sha256(senha.encode("utf-8")).hexdigest()
    return hmac.compare_digest(calculado, hash_hex.strip().lower())
