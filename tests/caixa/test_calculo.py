import json
from datetime import date
from decimal import Decimal

import pytest

from cfauto.caixa.calculo import (
    calcular_pagamento,
    calcular_sangria,
    descrever_venda,
    preco_de_venda,
    resumir,
    resumo_de_json,
    resumo_para_json,
    subtotal_item,
    troco,
    valor_cobrado,
    valor_desconto,
)
from cfauto.caixa.models import DESCRICAO_RECEBIMENTO, FormaPagamento, TipoVenda
from cfauto.caixa.schemas import (
    Desconto,
    MovimentoResumo,
    TaxaForma,
    TipoDesconto,
    TotaisForma,
)
from cfauto.core.errors import ValorInvalido

D = Decimal
HOJE = date(2026, 9, 23)
DINHEIRO = FormaPagamento.DINHEIRO
PIX = FormaPagamento.PIX
DEBITO = FormaPagamento.DEBITO
CREDITO = FormaPagamento.CREDITO
CREDIARIO = FormaPagamento.CREDIARIO
VENDA = TipoVenda.VENDA
RECEBIMENTO = TipoVenda.RECEBIMENTO


def _taxa(forma, pct, dias, repasse=False):
    return TaxaForma(forma=forma, pct=D(pct), dias=dias, repasse=repasse)


def _mov(tipo, forma, bruto, taxa="0", repasse=False, cancelada=False):
    bruto_d, taxa_d = D(bruto), D(taxa)
    liquido = bruto_d if repasse else bruto_d - taxa_d
    return MovimentoResumo(
        tipo=tipo,
        forma=forma,
        bruto=bruto_d,
        taxa=taxa_d,
        liquido=liquido,
        repasse=repasse,
        cancelada=cancelada,
    )


def _movimentos_do_dia():
    return [
        _mov(VENDA, DINHEIRO, "30.00"),
        _mov(VENDA, DEBITO, "100.00", "1.50"),
        _mov(VENDA, DEBITO, "50.00", "0.75", repasse=True),
        _mov(VENDA, CREDIARIO, "80.00"),
        _mov(RECEBIMENTO, DINHEIRO, "40.00"),
        _mov(RECEBIMENTO, PIX, "20.00"),
        _mov(VENDA, DINHEIRO, "25.00", cancelada=True),
    ]


def test_subtotal_item_arredonda_meio_para_cima():
    assert subtotal_item(D("1.5"), D("3.33")) == D("5.00")  # 4,995
    assert subtotal_item(D("2"), D("30.00")) == D("60.00")


@pytest.mark.parametrize(
    ("desconto", "esperado"),
    [
        (Desconto(), D("0.00")),
        (Desconto(TipoDesconto.REAIS, D("10")), D("10.00")),
        (Desconto(TipoDesconto.REAIS, D("99.99")), D("99.99")),
        (Desconto(TipoDesconto.PERCENTUAL, D("10")), D("10.00")),  # 9,999
        (Desconto(TipoDesconto.PERCENTUAL, D("100")), D("99.99")),
        (Desconto(TipoDesconto.PERCENTUAL, D("0")), D("0.00")),
    ],
)
def test_valor_desconto(desconto, esperado):
    assert valor_desconto(D("99.99"), desconto) == esperado


@pytest.mark.parametrize(
    "desconto",
    [
        Desconto(TipoDesconto.REAIS, D("100.00")),
        Desconto(TipoDesconto.REAIS, D("-1")),
        Desconto(TipoDesconto.PERCENTUAL, D("100.01")),
        Desconto(TipoDesconto.PERCENTUAL, D("-5")),
    ],
)
def test_desconto_fora_da_faixa(desconto):
    with pytest.raises(ValorInvalido, match="Desconto"):
        valor_desconto(D("99.99"), desconto)


def test_debito_sem_repasse_desconta_a_taxa_da_loja():
    pg = calcular_pagamento(D("100.00"), DEBITO, _taxa(DEBITO, "1.5", 7), HOJE)
    assert (pg.taxa, pg.liquido, pg.cobrado, pg.repasse, pg.data_liquidacao) == (
        D("1.50"),
        D("98.50"),
        D("100.00"),
        False,
        date(2026, 9, 30),
    )


def test_repasse_cliente_paga_a_taxa():
    pg = calcular_pagamento(D("100.00"), CREDITO, _taxa(CREDITO, "3.5", 7, True), HOJE)
    assert (pg.taxa, pg.liquido, pg.cobrado, pg.repasse) == (
        D("3.50"),
        D("100.00"),
        D("103.50"),
        True,
    )


def test_taxa_zero_e_dias_zero_sao_respeitados():
    pg = calcular_pagamento(D("80.00"), DEBITO, _taxa(DEBITO, "0", 0), HOJE)
    assert (pg.taxa, pg.liquido, pg.cobrado, pg.data_liquidacao) == (
        D("0.00"),
        D("80.00"),
        D("80.00"),
        HOJE,
    )


def test_taxa_arredonda_no_total_da_venda():
    # 3 itens de R$ 0,50 a 3,5%: por item daria 3 × 0,02 = 0,06; no total, 0,0525 → 0,05.
    pg = calcular_pagamento(D("1.50"), CREDITO, _taxa(CREDITO, "3.5", 7), HOJE)
    assert pg.taxa == D("0.05")


def test_crediario_sem_taxa_nem_liquidacao():
    pg = calcular_pagamento(D("80.00"), CREDIARIO, None, HOJE)
    assert (pg.taxa, pg.liquido, pg.cobrado, pg.repasse, pg.data_liquidacao) == (
        D("0.00"),
        D("80.00"),
        D("80.00"),
        False,
        None,
    )


def test_forma_sem_taxa_configurada():
    with pytest.raises(ValorInvalido, match="Taxa não configurada para Débito"):
        calcular_pagamento(D("10.00"), DEBITO, None, HOJE)


def test_valor_cobrado():
    assert valor_cobrado(D("100.00"), D("1.50"), True) == D("101.50")
    assert valor_cobrado(D("100.00"), D("1.50"), False) == D("100.00")


def test_troco():
    assert troco(D("47.50"), D("50")) == D("2.50")
    assert troco(D("47.50"), D("47.50")) == D("0.00")
    with pytest.raises(ValorInvalido, match="menor que o total"):
        troco(D("47.50"), D("40"))


def test_resumo_separa_recebimentos_e_ignora_canceladas():
    r = resumir(D("100.00"), _movimentos_do_dia())
    assert list(r.vendas) == [DINHEIRO, DEBITO, CREDIARIO]  # ordem do enum
    assert r.vendas[DINHEIRO] == TotaisForma(1, D("30.00"), D("0"), D("30.00"), D("30.00"))
    assert r.vendas[DEBITO] == TotaisForma(2, D("150.00"), D("2.25"), D("148.50"), D("150.75"))
    assert r.vendas[CREDIARIO] == TotaisForma(1, D("80.00"), D("0"), D("80.00"), D("80.00"))
    assert r.recebimentos == {
        DINHEIRO: TotaisForma(1, D("40.00"), D("0"), D("40.00"), D("40.00")),
        PIX: TotaisForma(1, D("20.00"), D("0"), D("20.00"), D("20.00")),
    }
    assert (r.canceladas_qtd, r.canceladas_bruto) == (1, D("25.00"))
    assert r.total_vendido == D("260.00")  # sem recebimentos, com crediário
    assert (r.dinheiro, r.gaveta) == (D("70.00"), D("170.00"))  # venda 30 + recebimento 40


def test_resumo_de_sessao_vazia():
    r = resumir(D("50.00"), [])
    assert (r.vendas, r.recebimentos, r.canceladas_qtd) == ({}, {}, 0)
    assert (r.total_vendido, r.dinheiro, r.gaveta) == (D("0"), D("0"), D("50.00"))


def test_gaveta_conta_o_cobrado_em_dinheiro_com_repasse():
    r = resumir(D("0"), [_mov(VENDA, DINHEIRO, "10.00", "1.00", repasse=True)])
    assert (r.dinheiro, r.gaveta) == (D("11.00"), D("11.00"))


def test_sangria():
    assert calcular_sangria(D("170.00"), D("100")) == D("70.00")
    assert calcular_sangria(D("170.00"), D("170.00")) == D("0.00")
    assert calcular_sangria(D("170.00"), D("0")) == D("170.00")
    with pytest.raises(ValorInvalido, match="negativo"):
        calcular_sangria(D("170.00"), D("-1"))
    with pytest.raises(ValorInvalido, match="gaveta"):
        calcular_sangria(D("170.00"), D("170.01"))


def test_descrever_venda():
    assert descrever_venda(VENDA, ["Óleo 5W30"]) == "Óleo 5W30"
    assert descrever_venda(VENDA, ["Óleo 5W30", "Filtro"]) == "Óleo 5W30 (+1 item)"
    assert descrever_venda(VENDA, ["Óleo 5W30", "Filtro", "Troca"]) == "Óleo 5W30 (+2 itens)"
    assert descrever_venda(RECEBIMENTO, []) == DESCRICAO_RECEBIMENTO


def test_resumo_json_ida_e_volta():
    resumo = resumir(D("100.00"), _movimentos_do_dia())
    dados = resumo_para_json(resumo)
    json.dumps(dados)  # serializável sem conversor
    assert dados["vendas"]["DEBITO"]["bruto"] == "150.00"
    assert dados["gaveta"] == "170.00"
    assert resumo_de_json(dados) == resumo


@pytest.mark.parametrize("promocional", [D("35.00"), D("0.00")])
def test_preco_de_venda_usa_o_promocional_quando_informado(promocional):
    # Só `None` significa "sem promoção": a função não compara valores nem testa zero.
    assert preco_de_venda(D("30.00"), promocional) == promocional


def test_preco_de_venda_sem_promocional_usa_o_de_venda():
    assert preco_de_venda(D("30.00"), None) == D("30.00")


def test_preco_de_venda_promocional_menor_que_o_de_venda():
    assert preco_de_venda(D("30.00"), D("25.00")) == D("25.00")
