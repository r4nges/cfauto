"""Venda no PDV: carrinho misto (produto + serviço), taxa por forma e crediário no razão."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.caixa.calculo import (
    calcular_pagamento,
    descrever_venda,
    preco_de_venda,
    subtotal_item,
    valor_cobrado,
    valor_desconto,
)
from cfauto.caixa.models import CATEGORIA_SERVICO, FormaPagamento, TipoVenda, Venda, VendaItem
from cfauto.caixa.schemas import LinhaVenda, NovaVenda
from cfauto.caixa.sessao import carregar_sessao_aberta, exigir_sessao_aberta, nome_usuario
from cfauto.caixa.taxas import taxa_da_forma
from cfauto.clientes.models import Cliente, MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar
from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import EstoqueInsuficiente, LimiteExcedido, PermissaoNegada, ValorInvalido
from cfauto.core.money import arredondar_qtd, formatar_brl, formatar_qtd
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo
from cfauto.estoque.models import Produto, Servico, TipoMovimento
from cfauto.estoque.movimentos import movimentar


@dataclass(frozen=True)
class _ItemMontado:
    produto: Produto | None
    servico_id: int | None
    descricao: str
    categoria: str
    qtd: Decimal
    preco_unit: Decimal
    subtotal: Decimal


def admin_responsavel(ator: Ator, autorizador: Ator | None) -> int | None:
    """Admin que responde por uma ação só-admin: o logado, ou quem autorizou pela senha."""
    if ator.admin:
        return ator.id
    if autorizador is None:
        return None
    if not autorizador.admin:
        raise PermissaoNegada("Autorização exige um administrador.")
    return autorizador.id


def _montar_itens(s: Session, dados: NovaVenda) -> list[_ItemMontado]:
    """Preço e descrição vêm sempre do banco, nunca da tela."""
    if not dados.itens:
        raise ValorInvalido("Carrinho vazio: adicione ao menos um item.")
    itens: list[_ItemMontado] = []
    for item in dados.itens:
        qtd = arredondar_qtd(item.qtd)
        if qtd <= 0:
            raise ValorInvalido("A quantidade de cada item deve ser maior que zero.")
        if (item.produto_id is None) == (item.servico_id is None):
            raise ValorInvalido("Cada item deve ser um produto ou um serviço.")
        if item.produto_id is not None:
            produto = s.get(Produto, item.produto_id)
            if produto is None:
                raise ValorInvalido("Produto não encontrado.")
            if not produto.ativo:
                raise ValorInvalido(f"Produto inativo: {produto.descricao}.")
            preco = preco_de_venda(produto.preco_venda, produto.preco_promocional)
            itens.append(
                _ItemMontado(
                    produto=produto,
                    servico_id=None,
                    descricao=produto.descricao,
                    categoria=produto.categoria,
                    qtd=qtd,
                    preco_unit=preco,
                    subtotal=subtotal_item(qtd, preco),
                )
            )
        else:
            servico = s.get(Servico, item.servico_id)
            if servico is None:
                raise ValorInvalido("Serviço não encontrado.")
            if not servico.ativo:
                raise ValorInvalido(f"Serviço inativo: {servico.nome}.")
            preco = servico.preco
            itens.append(
                _ItemMontado(
                    produto=None,
                    servico_id=servico.id,
                    descricao=servico.nome,
                    categoria=CATEGORIA_SERVICO,
                    qtd=qtd,
                    preco_unit=preco,
                    subtotal=subtotal_item(qtd, preco),
                )
            )
    return itens


def _faltas_de_estoque(itens: list[_ItemMontado]) -> tuple[str, ...]:
    """Soma o mesmo produto repetido no carrinho antes de comparar com o estoque."""
    pedidos: dict[int, Decimal] = defaultdict(Decimal)
    produtos: dict[int, Produto] = {}
    for item in itens:
        if item.produto is not None:
            pedidos[item.produto.id] += item.qtd
            produtos[item.produto.id] = item.produto
    return tuple(
        f"{p.codigo} {p.descricao}: estoque {formatar_qtd(p.estoque)}, "
        f"pedido {formatar_qtd(pedidos[pid])}"
        for pid, p in produtos.items()
        if pedidos[pid] > p.estoque
    )


def _cliente_ativo(s: Session, cliente_id: int | None) -> Cliente | None:
    if cliente_id is None:
        return None
    cliente = s.get(Cliente, cliente_id)
    if cliente is None:
        raise ValorInvalido("Cliente não encontrado.")
    if not cliente.ativo:
        raise ValorInvalido("Cliente inativo: reative antes de vender.")
    return cliente


def registrar_venda(
    s: Session,
    ator: Ator,
    dados: NovaVenda,
    *,
    autorizador: Ator | None = None,
    confirmar_limite: bool = False,
    confirmar_estoque: bool = False,
) -> int:
    """Grava venda, itens, baixa de estoque e (no crediário) o débito no razão, numa transação.

    Estoque insuficiente (para qualquer usuário, inclusive admin) e limite excedido levantam
    erro antes de gravar qualquer coisa; a UI confirma e reenvia a mesma venda com
    `confirmar_estoque=True` (+ `autorizador` se o logado não é admin) / `confirmar_limite=True`.
    """
    exigir_modulo(ator, Modulo.PDV)
    sessao = exigir_sessao_aberta(s)
    itens = _montar_itens(s, dados)
    cliente = _cliente_ativo(s, dados.cliente_id)
    crediario = dados.forma == FormaPagamento.CREDIARIO
    if crediario:
        if cliente is None:
            raise ValorInvalido("Venda no crediário exige um cliente.")
        if dados.desconto.valor != 0:
            raise ValorInvalido("Venda no crediário não aceita desconto.")
    subtotal = sum((item.subtotal for item in itens), Decimal("0.00"))
    desconto = valor_desconto(subtotal, dados.desconto)
    bruto = subtotal - desconto
    faltas = _faltas_de_estoque(itens)
    autorizado_por: int | None = None
    if faltas:
        # Autorizador que não é admin → PermissaoNegada, com ou sem a confirmação.
        responsavel = admin_responsavel(ator, autorizador)
        if not confirmar_estoque or responsavel is None:
            raise EstoqueInsuficiente(
                "Estoque insuficiente: "
                + "; ".join(faltas)
                + ". Vender mesmo assim exige confirmação de um administrador.",
                faltas,
            )
        autorizado_por = responsavel
    limite_excedido: dict[str, Decimal] | None = None
    if crediario and cliente is not None:
        if bruto <= 0:
            raise ValorInvalido("Venda no crediário precisa ter valor maior que zero.")
        disponivel = cliente.disponivel
        if disponivel is not None and bruto > disponivel:
            excesso = bruto - disponivel
            if not confirmar_limite:
                raise LimiteExcedido(
                    f"Venda excede o limite do cliente em {formatar_brl(excesso)} "
                    f"(disponível {formatar_brl(disponivel)}).",
                    disponivel,
                    excesso,
                )
            limite_excedido = {"disponivel": disponivel, "excesso": excesso}
    agora = clock.agora()
    pagamento = calcular_pagamento(bruto, dados.forma, taxa_da_forma(s, dados.forma), agora.date())
    venda = Venda(
        sessao_id=sessao.id,
        data_hora=agora,
        usuario_id=ator.id,
        autorizado_por=autorizado_por,
        cliente_id=None if cliente is None else cliente.id,
        tipo=TipoVenda.VENDA,
        forma_pagamento=dados.forma,
        desconto=desconto,
        bruto=bruto,
        taxa=pagamento.taxa,
        liquido=pagamento.liquido,
        repasse_taxa=pagamento.repasse,
        data_liquidacao=pagamento.data_liquidacao,
        cancelada=False,
        itens=[
            VendaItem(
                produto_id=None if item.produto is None else item.produto.id,
                servico_id=item.servico_id,
                descricao_snapshot=item.descricao,
                categoria_snapshot=item.categoria,
                qtd=item.qtd,
                preco_unit=item.preco_unit,
                subtotal=item.subtotal,
            )
            for item in itens
        ],
    )
    s.add(venda)
    s.flush()
    for montado, gravado in zip(itens, venda.itens, strict=True):
        if montado.produto is not None:
            movimentar(
                s,
                ator,
                montado.produto,
                -montado.qtd,
                TipoMovimento.VENDA,
                observacao=f"Venda nº {venda.id}",
                venda_item_id=gravado.id,
            )
    if crediario and cliente is not None:
        lancar(
            s,
            ator,
            cliente,
            TipoLancamento.DEBITO,
            bruto,
            MotivoLancamento.VENDA_CREDIARIO,
            f"Venda nº {venda.id}",
            venda_id=venda.id,
        )
    depois: dict[str, Any] = {
        "tipo": venda.tipo,
        "forma": venda.forma_pagamento,
        "cliente_id": venda.cliente_id,
        "desconto": venda.desconto,
        "bruto": venda.bruto,
        "taxa": venda.taxa,
        "liquido": venda.liquido,
        "repasse_taxa": venda.repasse_taxa,
        "autorizado_por": venda.autorizado_por,
        "itens": [
            {
                "produto_id": i.produto_id,
                "servico_id": i.servico_id,
                "qtd": i.qtd,
                "preco_unit": i.preco_unit,
                "subtotal": i.subtotal,
            }
            for i in venda.itens
        ],
        "limite_excedido": limite_excedido,
    }
    registrar(s, ator.id, "criar", "venda", venda.id, None, depois)
    return venda.id


def _linha_venda(s: Session, venda: Venda) -> LinhaVenda:
    cliente = None if venda.cliente_id is None else s.get(Cliente, venda.cliente_id)
    return LinhaVenda(
        id=venda.id,
        data_hora=venda.data_hora,
        tipo=venda.tipo,
        forma=venda.forma_pagamento,
        cliente=None if cliente is None else cliente.nome,
        descricao=descrever_venda(venda.tipo, [i.descricao_snapshot for i in venda.itens]),
        bruto=venda.bruto,
        taxa=venda.taxa,
        liquido=venda.liquido,
        cobrado=valor_cobrado(venda.bruto, venda.taxa, venda.repasse_taxa),
        usuario=nome_usuario(s, venda.usuario_id) or "",
        cancelada=venda.cancelada,
    )


def vendas_da_sessao(s: Session, ator: Ator) -> list[LinhaVenda]:
    """Vendas e recebimentos da sessão aberta, mais recentes primeiro (inclui canceladas)."""
    exigir_modulo(ator, Modulo.PDV)
    sessao = carregar_sessao_aberta(s)
    if sessao is None:
        return []
    vendas = s.scalars(
        select(Venda)
        .where(Venda.sessao_id == sessao.id)
        .order_by(Venda.data_hora.desc(), Venda.id.desc())
    )
    return [_linha_venda(s, venda) for venda in vendas]
