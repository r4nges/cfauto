"""Códigos de negócio sequenciais (0001, SERV-001, BEM-001), nunca reaproveitados."""

from sqlalchemy.orm import Session

from cfauto.core.models import Sequencia


def proximo_codigo(s: Session, nome: str, *, prefixo: str = "", digitos: int) -> str:
    sequencia = s.get(Sequencia, nome)
    if sequencia is None:
        sequencia = Sequencia(nome=nome, ultimo=0)
        s.add(sequencia)
    sequencia.ultimo += 1
    s.flush()
    return f"{prefixo}{sequencia.ultimo:0{digitos}d}"
