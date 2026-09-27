"""Única porta de alteração do saldo de estoque: todo movimento fica registrado."""

from decimal import Decimal

from sqlalchemy.orm import Session

from cfauto.core import clock
from cfauto.core.errors import ValorInvalido
from cfauto.core.money import arredondar_qtd
from cfauto.core.permissoes import Ator
from cfauto.estoque.models import (
    MotivoAjuste,
    MovimentoEstoque,
    NotaEntradaItem,
    Produto,
    TipoMovimento,
)


def movimentar(
    s: Session,
    ator: Ator,
    produto: Produto,
    quantidade: Decimal,
    tipo: TipoMovimento,
    *,
    motivo: MotivoAjuste | None = None,
    observacao: str | None = None,
    nota_item: NotaEntradaItem | None = None,
) -> MovimentoEstoque:
    """Soma `quantidade` (com sinal) ao estoque. Não checa permissão nem saldo negativo:
    quem chama decide."""
    quantidade = arredondar_qtd(quantidade)
    if quantidade == 0:
        raise ValorInvalido("Movimento de estoque com quantidade zero.")
    produto.estoque = produto.estoque + quantidade
    movimento = MovimentoEstoque(
        produto_id=produto.id,
        data_hora=clock.agora(),
        tipo=tipo,
        quantidade=quantidade,
        saldo_apos=produto.estoque,
        usuario_id=ator.id,
        motivo=motivo,
        observacao=observacao,
        nota_entrada_item_id=None if nota_item is None else nota_item.id,
    )
    s.add(movimento)
    s.flush()
    return movimento
