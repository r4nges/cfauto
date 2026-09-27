"""Entradas dos serviços do painel CFAUTO."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from cfauto.gestao.models import TipoBem


@dataclass(frozen=True)
class DadosBem:
    descricao: str
    tipo: TipoBem
    valor: Decimal
    # None: hoje na criação; mantém a data atual na edição.
    data_cadastro: date | None = None
