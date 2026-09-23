from typing import Any

from sqlalchemy.orm import Session

from cfauto.core.audit import registrar
from cfauto.core.jsonutil import para_json
from cfauto.core.models import ConfigItem
from cfauto.core.permissoes import Ator


def obter(s: Session, chave: str, padrao: Any = None) -> Any:
    item = s.get(ConfigItem, chave)
    return padrao if item is None else item.valor


def definir(
    s: Session, chave: str, valor: Any, *, ator: Ator | None = None, auditar: bool = False
) -> None:
    item = s.get(ConfigItem, chave)
    antes = None if item is None else item.valor
    novo = para_json(valor)
    if item is None:
        s.add(ConfigItem(chave=chave, valor=novo))
    else:
        item.valor = novo
    s.flush()
    if auditar:
        registrar(
            s,
            ator.id if ator else None,
            "alterar",
            "config",
            chave,
            {"valor": antes},
            {"valor": novo},
        )
