import hashlib

from cfauto.auth.senha import gerar_hash, precisa_rehash, verificar, verificar_legado


def test_hash_argon2():
    h = gerar_hash("segredo1")
    assert h.startswith("$argon2id$")
    assert verificar(h, "segredo1")
    assert not verificar(h, "errada")
    assert not precisa_rehash(h)


def test_hash_invalido_nao_explode():
    assert verificar("lixo", "x") is False


def test_legado_sha256():
    legado = hashlib.sha256(b"abc123").hexdigest().upper()
    assert verificar_legado(legado, "abc123")
    assert not verificar_legado(legado, "abc124")
