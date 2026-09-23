import hashlib
from datetime import datetime

import pytest
from sqlalchemy import select

from cfauto.auth.models import Usuario
from cfauto.auth.service import (
    AlteracaoUsuario,
    NovoUsuario,
    alterar_senha,
    atualizar_usuario,
    autenticar,
    criar_usuario,
    existe_usuario,
    listar_usuarios,
)
from cfauto.core.db import transacao
from cfauto.core.errors import (
    CredenciaisInvalidas,
    LoginDuplicado,
    PermissaoNegada,
    UsuarioBloqueado,
    ValorInvalido,
)
from cfauto.core.models import AuditLog
from cfauto.core.permissoes import Modulo


def test_primeiro_usuario_sem_ator_deve_ser_admin(sessao):
    assert not existe_usuario(sessao)
    with pytest.raises(ValorInvalido):
        criar_usuario(sessao, None, NovoUsuario(nome="X", login="x", senha="123456"))


def test_segundo_usuario_sem_ator_negado(sessao, admin):
    with pytest.raises(PermissaoNegada):
        criar_usuario(sessao, None, NovoUsuario(nome="Y", login="y", senha="123456", admin=True))


def test_login_normalizado_e_unico(sessao, admin):
    assert admin.login == "dono"
    with pytest.raises(LoginDuplicado):
        criar_usuario(sessao, admin, NovoUsuario(nome="Outro", login="  DONO ", senha="123456"))


def test_senha_curta(sessao, admin):
    with pytest.raises(ValorInvalido):
        criar_usuario(sessao, admin, NovoUsuario(nome="Z", login="z", senha="12345"))


def test_operador_nao_cria_usuario(sessao, operador):
    with pytest.raises(PermissaoNegada):
        criar_usuario(sessao, operador, NovoUsuario(nome="Z", login="z", senha="123456"))


def test_autenticar_ok(sessao, operador):
    ator = autenticar(sessao, " Maria ", "segredo2")
    assert ator.id == operador.id
    assert ator.modulos == frozenset({Modulo.PDV, Modulo.CLIENTES})
    assert ator.admin is False


def test_autenticar_usuario_inexistente(sessao):
    with pytest.raises(CredenciaisInvalidas):
        autenticar(sessao, "ninguem", "x")


def test_bloqueio_apos_cinco_falhas_persiste(fabrica, relogio):
    with transacao(fabrica) as s:
        criar_usuario(s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True))
    for _ in range(5):
        with pytest.raises(CredenciaisInvalidas), transacao(fabrica) as s:
            autenticar(s, "dono", "errada")
    with pytest.raises(UsuarioBloqueado) as erro, transacao(fabrica) as s:
        autenticar(s, "dono", "segredo1")
    assert erro.value.ate == datetime(2026, 9, 23, 10, 5)
    relogio.avancar(minutes=5, seconds=1)
    with transacao(fabrica) as s:
        assert autenticar(s, "dono", "segredo1").login == "dono"


def test_sucesso_zera_falhas(fabrica, relogio):
    with transacao(fabrica) as s:
        criar_usuario(s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True))
    for _ in range(4):
        with pytest.raises(CredenciaisInvalidas), transacao(fabrica) as s:
            autenticar(s, "dono", "errada")
    with transacao(fabrica) as s:
        autenticar(s, "dono", "segredo1")
    with pytest.raises(CredenciaisInvalidas), transacao(fabrica) as s:
        autenticar(s, "dono", "errada")
    with transacao(fabrica) as s:
        u = s.scalar(select(Usuario).where(Usuario.login == "dono"))
        assert u.tentativas_falhas == 1


def test_hash_legado_regravado_em_argon2(sessao, admin):
    u = Usuario(
        nome="Antigo",
        login="antigo",
        senha_hash=None,
        hash_legado=hashlib.sha256(b"abc123").hexdigest(),
        modulos=["PDV"],
    )
    sessao.add(u)
    sessao.flush()
    autenticar(sessao, "antigo", "abc123")
    assert u.hash_legado is None
    assert u.senha_hash.startswith("$argon2id$")
    assert autenticar(sessao, "antigo", "abc123").login == "antigo"


def test_inativo_nao_entra(sessao, admin, operador):
    atualizar_usuario(
        sessao,
        admin,
        operador.id,
        AlteracaoUsuario(nome="Maria", funcao="", admin=False, modulos=frozenset(), ativo=False),
    )
    with pytest.raises(CredenciaisInvalidas):
        autenticar(sessao, "maria", "segredo2")


def test_nao_remove_ultimo_admin(sessao, admin):
    with pytest.raises(ValorInvalido):
        atualizar_usuario(
            sessao,
            admin,
            admin.id,
            AlteracaoUsuario(nome="Dono", funcao="", admin=False, modulos=frozenset(), ativo=True),
        )


def test_atualizar_modulos(sessao, admin, operador):
    novo = atualizar_usuario(
        sessao,
        admin,
        operador.id,
        AlteracaoUsuario(
            nome="Maria S.",
            funcao="Caixa",
            admin=False,
            modulos=frozenset({Modulo.ESTOQUE}),
            ativo=True,
        ),
    )
    assert novo.nome == "Maria S."
    assert novo.modulos == frozenset({Modulo.ESTOQUE})


def test_alterar_senha(sessao, admin, operador):
    alterar_senha(sessao, operador, operador.id, "novasenha")
    assert autenticar(sessao, "maria", "novasenha").id == operador.id
    with pytest.raises(PermissaoNegada):
        alterar_senha(sessao, operador, admin.id, "hackeada")
    alterar_senha(sessao, admin, operador.id, "outra123")
    assert autenticar(sessao, "maria", "outra123").id == operador.id


def test_listar_so_admin(sessao, admin, operador):
    assert [u.login for u in listar_usuarios(sessao, admin)] == ["dono", "maria"]
    with pytest.raises(PermissaoNegada):
        listar_usuarios(sessao, operador)


def test_auditoria_sem_senha(sessao, admin, operador):
    regs = sessao.scalars(select(AuditLog).where(AuditLog.entidade == "usuario")).all()
    assert [r.acao for r in regs] == ["criar", "criar"]
    for r in regs:
        assert "senha" not in r.depois
        assert "senha_hash" not in r.depois
    assert regs[1].depois["modulos"] == ["CLIENTES", "PDV"]
