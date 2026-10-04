"""Receber crediário: entra no caixa pela forma real e abate a dívida no razão do cliente."""

from decimal import Decimal

from sqlalchemy.orm import Session

from cfauto.caixa.calculo import calcular_pagamento
from cfauto.caixa.models import FORMAS_COM_TAXA, FormaPagamento, TipoVenda, Venda
from cfauto.caixa.sessao import exigir_sessao_aberta
from cfauto.caixa.taxas import taxa_da_forma
from cfauto.clientes.cadastro import carregar_cliente
from cfauto.clientes.models import MotivoLancamento, TipoLancamento
from cfauto.clientes.razao import lancar
from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import ValorInvalido
from cfauto.core.money import arredondar
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo


def registrar_recebimento(
    s: Session, ator: Ator, cliente_id: int, valor: Decimal, forma: FormaPagamento
) -> int:
    """Com repasse, o cliente paga valor + taxa e a dívida abate `valor`. Valor maior que a
    dívida é aceito e vira crédito a favor (saldo negativo)."""
    exigir_modulo(ator, Modulo.PDV)
    sessao = exigir_sessao_aberta(s)
    if forma not in FORMAS_COM_TAXA:
        raise ValorInvalido("Recebimento aceita só dinheiro, PIX, débito ou crédito.")
    valor = arredondar(valor)
    if valor <= 0:
        raise ValorInvalido("O valor do recebimento deve ser maior que zero.")
    cliente = carregar_cliente(s, cliente_id)
    if not cliente.ativo:
        raise ValorInvalido("Cliente inativo: reative antes de receber.")
    agora = clock.agora()
    pagamento = calcular_pagamento(valor, forma, taxa_da_forma(s, forma), agora.date())
    venda = Venda(
        sessao_id=sessao.id,
        data_hora=agora,
        usuario_id=ator.id,
        autorizado_por=None,
        cliente_id=cliente.id,
        tipo=TipoVenda.RECEBIMENTO,
        forma_pagamento=forma,
        desconto=Decimal("0.00"),
        bruto=valor,
        taxa=pagamento.taxa,
        liquido=pagamento.liquido,
        repasse_taxa=pagamento.repasse,
        data_liquidacao=pagamento.data_liquidacao,
        cancelada=False,
    )
    s.add(venda)
    s.flush()
    lancar(
        s,
        ator,
        cliente,
        TipoLancamento.CREDITO,
        valor,
        MotivoLancamento.RECEBIMENTO,
        f"Recebimento nº {venda.id}",
        venda_id=venda.id,
    )
    registrar(
        s,
        ator.id,
        "criar",
        "venda",
        venda.id,
        None,
        {
            "tipo": venda.tipo,
            "forma": venda.forma_pagamento,
            "cliente_id": cliente.id,
            "bruto": venda.bruto,
            "taxa": venda.taxa,
            "liquido": venda.liquido,
            "repasse_taxa": venda.repasse_taxa,
            "saldo_devedor_apos": cliente.saldo_devedor,
        },
    )
    return venda.id
