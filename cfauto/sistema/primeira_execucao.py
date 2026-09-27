from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy.orm import Session

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core import config
from cfauto.core.permissoes import Ator
from cfauto.licenca.service import instalar


@dataclass(frozen=True)
class DadosPrimeiraExecucao:
    nome: str
    login: str
    senha: str
    chave_licenca: str
    empresa_nome: str
    empresa_cnpj: str = ""


def concluir(
    s: Session,
    dados: DadosPrimeiraExecucao,
    *,
    publica: Ed25519PublicKey | None = None,
    maquina_atual: str | None = None,
) -> Ator:
    """Cria o admin, instala a licença e grava a empresa numa única transação."""
    ator = criar_usuario(
        s, None, NovoUsuario(nome=dados.nome, login=dados.login, senha=dados.senha, admin=True)
    )
    instalar(s, dados.chave_licenca, publica=publica, maquina_atual=maquina_atual)
    config.definir(s, "empresa.nome", dados.empresa_nome.strip(), ator=ator, auditar=True)
    config.definir(s, "empresa.cnpj", dados.empresa_cnpj.strip(), ator=ator, auditar=True)
    return ator
