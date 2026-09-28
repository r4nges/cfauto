"""Entradas e saídas dos serviços de Clientes (a UI não recebe entidade ORM)."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from cfauto.clientes.models import (
    LIMITE_PADRAO,
    FrequenciaJuros,
    MotivoLancamento,
    Sexo,
    TipoLancamento,
)


@dataclass(frozen=True)
class DadosDependente:
    nome: str
    parentesco: str = ""


@dataclass(frozen=True)
class DadosCliente:
    nome: str
    celular: str
    cpf: str = ""
    email: str = ""
    endereco: str = ""
    nascimento: date | None = None
    sexo: Sexo | None = None
    observacoes: str = ""
    # None = sem limite.
    limite: Decimal | None = LIMITE_PADRAO
    somente_titular: bool = False
    dependentes: tuple[DadosDependente, ...] = ()
    aumento_auto: bool = False
    aumento_auto_pct: Decimal = Decimal("5.00")
    juros_dias: int = 30
    juros_frequencia: FrequenciaJuros = FrequenciaJuros.MENSAL
    juros_pct: Decimal = Decimal("2.00")
    juros_mora: bool = False


@dataclass(frozen=True)
class ResumoCliente:
    id: int
    codigo: str
    nome: str
    celular: str
    cpf: str | None
    saldo_devedor: Decimal
    limite: Decimal | None
    disponivel: Decimal | None
    ativo: bool


@dataclass(frozen=True)
class FichaCliente:
    id: int
    codigo: str
    dados: DadosCliente
    saldo_devedor: Decimal
    disponivel: Decimal | None
    ativo: bool


@dataclass(frozen=True)
class LinhaLancamento:
    id: int
    data_hora: datetime
    tipo: TipoLancamento
    valor: Decimal
    saldo_apos: Decimal
    motivo: MotivoLancamento
    observacao: str
    usuario: str


@dataclass(frozen=True)
class Extrato:
    cliente: ResumoCliente
    inicio: date
    fim: date
    saldo_anterior: Decimal
    linhas: tuple[LinhaLancamento, ...]
    saldo_final: Decimal
