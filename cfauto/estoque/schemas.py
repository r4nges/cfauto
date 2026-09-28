"""Entradas e saídas dos serviços do Estoque, com tipos reais."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from cfauto.estoque.models import Destino, MotivoAjuste, TipoMovimento
from cfauto.estoque.nfe import ItemNotaLido, NotaFiscalLida


@dataclass(frozen=True)
class DadosProduto:
    descricao: str
    ean: str | None = None
    categoria: str = ""
    embalagem: str = "Unidade"
    fator: Decimal = Decimal(1)
    preco_entrada: Decimal = Decimal(0)
    preco_venda: Decimal = Decimal(0)
    preco_promocional: Decimal | None = None
    estoque_minimo: Decimal = Decimal(0)
    estoque_minimo_manual: bool = False
    destino: Destino = Destino.REVENDA
    # Só na criação; a edição nunca altera o estoque (use ajustar_estoque).
    estoque_inicial: Decimal = Decimal(0)


@dataclass(frozen=True)
class LinhaMovimento:
    data_hora: datetime
    tipo: TipoMovimento
    quantidade: Decimal
    saldo_apos: Decimal
    usuario_nome: str
    motivo: MotivoAjuste | None
    observacao: str | None
    nota: str | None


@dataclass(frozen=True)
class DadosMaterial:
    descricao: str
    custo_unit: Decimal
    qtd: Decimal = Decimal(1)


@dataclass(frozen=True)
class DadosServico:
    nome: str
    materiais: tuple[DadosMaterial, ...]
    mao_obra_pct: Decimal = Decimal(50)


class OrigemCasamento(StrEnum):
    VINCULO = "VINCULO"
    EAN = "EAN"
    EAN_TRIB = "EAN_TRIB"
    NENHUMA = "NENHUMA"


class AcaoItem(StrEnum):
    VINCULAR = "VINCULAR"
    CRIAR = "CRIAR"
    IGNORAR = "IGNORAR"


@dataclass(frozen=True)
class ItemConferencia:
    item: ItemNotaLido
    origem: OrigemCasamento
    fator_sugerido: Decimal
    produto_id: int | None = None
    produto_codigo: str | None = None
    produto_descricao: str | None = None


@dataclass(frozen=True)
class ConferenciaNota:
    nota: NotaFiscalLida
    itens: tuple[ItemConferencia, ...]
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisaoItem:
    n_item: int
    acao: AcaoItem
    produto_id: int | None = None  # VINCULAR
    descricao: str | None = None  # CRIAR; None = descrição da nota
    fator: Decimal | None = None  # VINCULAR e CRIAR
