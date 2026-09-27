"""Entradas e saídas dos serviços do Estoque, com tipos reais."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from cfauto.estoque.models import Destino, MotivoAjuste, TipoMovimento


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
