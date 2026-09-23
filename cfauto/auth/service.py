from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cfauto.auth import senha as senhas
from cfauto.auth.models import Usuario
from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import (
    CredenciaisInvalidas,
    LoginDuplicado,
    PermissaoNegada,
    RegistroNaoEncontrado,
    UsuarioBloqueado,
    ValorInvalido,
)
from cfauto.core.permissoes import Ator, Modulo, exigir_admin

MAX_TENTATIVAS = 5
TEMPO_BLOQUEIO = timedelta(minutes=5)
SENHA_MINIMA = 6


@dataclass(frozen=True)
class NovoUsuario:
    nome: str
    login: str
    senha: str
    admin: bool = False
    modulos: frozenset[Modulo] = field(default_factory=frozenset)
    funcao: str = ""


@dataclass(frozen=True)
class AlteracaoUsuario:
    nome: str
    funcao: str
    admin: bool
    modulos: frozenset[Modulo]
    ativo: bool


def para_ator(u: Usuario) -> Ator:
    return Ator(
        id=u.id,
        nome=u.nome,
        login=u.login,
        admin=u.admin,
        modulos=frozenset(Modulo(m) for m in u.modulos),
    )


def _snapshot(u: Usuario) -> dict[str, Any]:
    return {
        "nome": u.nome,
        "funcao": u.funcao,
        "login": u.login,
        "admin": u.admin,
        "modulos": sorted(u.modulos),
        "ativo": u.ativo,
    }


def _normalizar_login(login: str) -> str:
    normalizado = login.strip().lower()
    if not normalizado:
        raise ValorInvalido("Login obrigatório.")
    return normalizado


def _validar_senha(senha: str) -> None:
    if len(senha) < SENHA_MINIMA:
        raise ValorInvalido(f"A senha deve ter ao menos {SENHA_MINIMA} caracteres.")


def _obter(s: Session, usuario_id: int) -> Usuario:
    u = s.get(Usuario, usuario_id)
    if u is None:
        raise RegistroNaoEncontrado("Usuário não encontrado.")
    return u


def existe_usuario(s: Session) -> bool:
    return (s.scalar(select(func.count()).select_from(Usuario)) or 0) > 0


def criar_usuario(s: Session, ator: Ator | None, dados: NovoUsuario) -> Ator:
    if ator is None:
        if existe_usuario(s):
            raise PermissaoNegada("Já existem usuários; entre como administrador.")
        if not dados.admin:
            raise ValorInvalido("O primeiro usuário deve ser administrador.")
    else:
        exigir_admin(ator)
    nome = dados.nome.strip()
    if not nome:
        raise ValorInvalido("Nome obrigatório.")
    login = _normalizar_login(dados.login)
    _validar_senha(dados.senha)
    if s.scalar(select(Usuario.id).where(Usuario.login == login)) is not None:
        raise LoginDuplicado(f"O login '{login}' já existe.")
    u = Usuario(
        nome=nome,
        funcao=dados.funcao.strip(),
        login=login,
        senha_hash=senhas.gerar_hash(dados.senha),
        admin=dados.admin,
        modulos=sorted(m.value for m in dados.modulos),
    )
    s.add(u)
    s.flush()
    registrar(s, ator.id if ator else u.id, "criar", "usuario", u.id, None, _snapshot(u))
    return para_ator(u)


def autenticar(s: Session, login: str, senha: str) -> Ator:
    u = s.scalar(select(Usuario).where(Usuario.login == _normalizar_login(login)))
    if u is None or not u.ativo:
        raise CredenciaisInvalidas()
    agora = clock.agora()
    if u.bloqueado_ate is not None and u.bloqueado_ate > agora:
        raise UsuarioBloqueado(u.bloqueado_ate)
    if u.senha_hash:
        ok = senhas.verificar(u.senha_hash, senha)
        if ok and senhas.precisa_rehash(u.senha_hash):
            u.senha_hash = senhas.gerar_hash(senha)
    elif u.hash_legado:
        ok = senhas.verificar_legado(u.hash_legado, senha)
        if ok:
            u.senha_hash = senhas.gerar_hash(senha)
            u.hash_legado = None
    else:
        ok = False
    if not ok:
        u.tentativas_falhas += 1
        if u.tentativas_falhas >= MAX_TENTATIVAS:
            u.bloqueado_ate = agora + TEMPO_BLOQUEIO
            u.tentativas_falhas = 0
        s.commit()  # a falha precisa persistir mesmo com a exceção abaixo
        raise CredenciaisInvalidas()
    u.tentativas_falhas = 0
    u.bloqueado_ate = None
    s.flush()
    return para_ator(u)


def atualizar_usuario(s: Session, ator: Ator, usuario_id: int, dados: AlteracaoUsuario) -> Ator:
    exigir_admin(ator)
    u = _obter(s, usuario_id)
    if u.admin and u.ativo and (not dados.admin or not dados.ativo):
        outros = s.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(Usuario.admin.is_(True), Usuario.ativo.is_(True), Usuario.id != u.id)
        )
        if outros == 0:
            raise ValorInvalido("Deve existir ao menos um administrador ativo.")
    nome = dados.nome.strip()
    if not nome:
        raise ValorInvalido("Nome obrigatório.")
    antes = _snapshot(u)
    u.nome = nome
    u.funcao = dados.funcao.strip()
    u.admin = dados.admin
    u.modulos = sorted(m.value for m in dados.modulos)
    u.ativo = dados.ativo
    s.flush()
    registrar(s, ator.id, "alterar", "usuario", u.id, antes, _snapshot(u))
    return para_ator(u)


def alterar_senha(s: Session, ator: Ator, usuario_id: int, nova: str) -> None:
    if ator.id != usuario_id:
        exigir_admin(ator)
    _validar_senha(nova)
    u = _obter(s, usuario_id)
    u.senha_hash = senhas.gerar_hash(nova)
    u.hash_legado = None
    u.tentativas_falhas = 0
    u.bloqueado_ate = None
    s.flush()
    registrar(s, ator.id, "alterar_senha", "usuario", u.id)


def listar_usuarios(s: Session, ator: Ator) -> list[Usuario]:
    exigir_admin(ator)
    return list(s.scalars(select(Usuario).order_by(Usuario.nome)).all())
