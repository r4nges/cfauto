from datetime import date, datetime
from decimal import Decimal

import pytest

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.caixa.models import FormaPagamento, TipoVenda
from cfauto.caixa.recebimento import registrar_recebimento
from cfauto.caixa.schemas import Desconto, ItemVenda, NovaVenda, TipoDesconto
from cfauto.caixa.sessao import fechar_sessao
from cfauto.caixa.venda import cancelar_venda, registrar_venda
from cfauto.core.errors import PermissaoNegada, RegistroNaoEncontrado, ValorInvalido
from cfauto.core.permissoes import Modulo
from cfauto.historico.consultas import (
    FiltroHistorico,
    ItemDetalhe,
    detalhe_venda,
    listar_sessoes,
    listar_vendas,
)
from tests.fabricas import abrir_caixa, criar_cliente_teste, criar_produto, criar_servico

DINHEIRO = FormaPagamento.DINHEIRO
DEBITO = FormaPagamento.DEBITO
CREDIARIO = FormaPagamento.CREDIARIO
PIX = FormaPagamento.PIX
DIA = date(2026, 9, 23)


@pytest.fixture
def consultor(sessao, admin):
    return criar_usuario(
        sessao,
        admin,
        NovoUsuario(
            nome="Carla",
            login="carla",
            senha="segredo4",
            modulos=frozenset({Modulo.HISTORICO}),
        ),
    )


def _p(produto_id, qtd="1"):
    return ItemVenda(qtd=Decimal(qtd), produto_id=produto_id)


def _dia_fechado(sessao, admin, operador, relogio):
    """Sessão de 23/09 (10:00–18:40), fechada mantendo R$ 100:
    10:00 dinheiro Óleo + Troca de óleo com R$ 5 de desconto (bruto 55);
    10:10 débito 2× Óleo (bruto 60, taxa 0,90); 10:20 crediário 1× Óleo (30);
    10:30 recebimento de 30 em dinheiro; 10:40 PIX 1× Óleo, cancelada pelo admin."""
    pid = criar_produto(sessao, admin, estoque=Decimal("50"))
    sid = criar_servico(sessao, admin)
    cid = criar_cliente_teste(sessao, admin)
    abrir_caixa(sessao, operador)
    ids = {
        "dinheiro": registrar_venda(
            sessao,
            operador,
            NovaVenda(
                itens=(_p(pid), ItemVenda(qtd=Decimal("1"), servico_id=sid)),
                forma=DINHEIRO,
                desconto=Desconto(TipoDesconto.REAIS, Decimal("5")),
            ),
        )
    }
    relogio.avancar(minutes=10)
    ids["debito"] = registrar_venda(
        sessao, operador, NovaVenda(itens=(_p(pid, "2"),), forma=DEBITO)
    )
    relogio.avancar(minutes=10)
    ids["crediario"] = registrar_venda(
        sessao, operador, NovaVenda(itens=(_p(pid),), forma=CREDIARIO, cliente_id=cid)
    )
    relogio.avancar(minutes=10)
    ids["recebimento"] = registrar_recebimento(sessao, operador, cid, Decimal("30"), DINHEIRO)
    relogio.avancar(minutes=10)
    ids["cancelada"] = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=PIX))
    cancelar_venda(sessao, admin, ids["cancelada"], "Cliente desistiu")
    relogio.avancar(hours=8)
    fechar_sessao(sessao, operador, Decimal("100"))
    return ids, cid, pid


def test_lista_vendas_da_sessao_fechada(sessao, admin, operador, consultor, relogio):
    ids, _, _ = _dia_fechado(sessao, admin, operador, relogio)
    linhas = listar_vendas(sessao, consultor, FiltroHistorico(inicio=DIA, fim=DIA))
    assert [linha.venda_id for linha in linhas] == [
        ids["recebimento"],
        ids["crediario"],
        ids["debito"],
        ids["dinheiro"],
    ]
    por_id = {linha.venda_id: linha for linha in linhas}
    dinheiro = por_id[ids["dinheiro"]]
    assert (dinheiro.protocolo, dinheiro.data_hora, dinheiro.descricao) == (
        "CX-20260923-1000",
        datetime(2026, 9, 23, 10, 0),
        "Óleo 5W30 (+1 item)",
    )
    assert (dinheiro.bruto, dinheiro.taxa, dinheiro.liquido, dinheiro.dias_liquidacao) == (
        Decimal("55.00"),
        Decimal("0.00"),
        Decimal("55.00"),
        0,
    )
    assert (dinheiro.cliente, dinheiro.tipo, dinheiro.forma, dinheiro.cancelada) == (
        None,
        TipoVenda.VENDA,
        DINHEIRO,
        False,
    )
    debito = por_id[ids["debito"]]
    assert (debito.taxa, debito.liquido, debito.dias_liquidacao) == (
        Decimal("0.90"),
        Decimal("59.10"),
        7,
    )
    crediario = por_id[ids["crediario"]]
    assert (crediario.dias_liquidacao, crediario.cliente) == (None, "Ana Souza")
    recebimento = por_id[ids["recebimento"]]
    assert (recebimento.descricao, recebimento.tipo, recebimento.cliente) == (
        "RECEBIMENTO DE CONTA / FIADO",
        TipoVenda.RECEBIMENTO,
        "Ana Souza",
    )


def test_canceladas_so_com_o_filtro(sessao, admin, operador, consultor, relogio):
    ids, _, _ = _dia_fechado(sessao, admin, operador, relogio)
    linhas = listar_vendas(
        sessao, consultor, FiltroHistorico(inicio=DIA, fim=DIA, incluir_canceladas=True)
    )
    assert len(linhas) == 5
    assert (linhas[0].venda_id, linhas[0].cancelada) == (ids["cancelada"], True)


def test_filtros_de_forma_tipo_e_cliente(sessao, admin, operador, consultor, relogio):
    ids, cid, _ = _dia_fechado(sessao, admin, operador, relogio)
    por_forma = listar_vendas(sessao, consultor, FiltroHistorico(inicio=DIA, fim=DIA, forma=DEBITO))
    assert [linha.venda_id for linha in por_forma] == [ids["debito"]]
    por_tipo = listar_vendas(
        sessao, consultor, FiltroHistorico(inicio=DIA, fim=DIA, tipo=TipoVenda.RECEBIMENTO)
    )
    assert [linha.venda_id for linha in por_tipo] == [ids["recebimento"]]
    por_cliente = listar_vendas(
        sessao, consultor, FiltroHistorico(inicio=DIA, fim=DIA, cliente_id=cid)
    )
    assert [linha.venda_id for linha in por_cliente] == [ids["recebimento"], ids["crediario"]]


def test_filtro_de_periodo(sessao, admin, operador, consultor, relogio):
    ids, _, pid = _dia_fechado(sessao, admin, operador, relogio)
    relogio.avancar(days=1)
    abrir_caixa(sessao, operador)
    outro_dia = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))
    fechar_sessao(sessao, operador, Decimal("0"))
    dia_24 = date(2026, 9, 24)
    so_24 = listar_vendas(sessao, consultor, FiltroHistorico(inicio=dia_24, fim=dia_24))
    assert [linha.venda_id for linha in so_24] == [outro_dia]
    os_dois = listar_vendas(sessao, consultor, FiltroHistorico(inicio=DIA, fim=dia_24))
    assert len(os_dois) == 5
    assert os_dois[0].venda_id == outro_dia


def test_vendas_de_sessao_aberta_nao_aparecem(sessao, admin, operador, consultor, relogio):
    pid = criar_produto(sessao, admin)
    abrir_caixa(sessao, operador)
    aberta = registrar_venda(sessao, operador, NovaVenda(itens=(_p(pid),), forma=DINHEIRO))
    assert listar_vendas(sessao, consultor, FiltroHistorico(inicio=DIA, fim=DIA)) == []
    with pytest.raises(RegistroNaoEncontrado):
        detalhe_venda(sessao, consultor, aberta)


def test_detalhe_com_itens_desconto_e_cancelamento(sessao, admin, operador, consultor, relogio):
    ids, _, _ = _dia_fechado(sessao, admin, operador, relogio)
    detalhe = detalhe_venda(sessao, consultor, ids["dinheiro"])
    assert detalhe.itens == (
        ItemDetalhe(
            descricao="Óleo 5W30",
            categoria="Lubrificantes",
            qtd=Decimal("1.000"),
            preco_unit=Decimal("30.00"),
            subtotal=Decimal("30.00"),
        ),
        ItemDetalhe(
            descricao="Troca de óleo",
            categoria="Serviço",
            qtd=Decimal("1.000"),
            preco_unit=Decimal("30.00"),
            subtotal=Decimal("30.00"),
        ),
    )
    assert (detalhe.desconto, detalhe.usuario, detalhe.autorizado_por) == (
        Decimal("5.00"),
        "Maria",
        None,
    )
    assert detalhe.linha.venda_id == ids["dinheiro"]
    cancelada = detalhe_venda(sessao, consultor, ids["cancelada"])
    assert (
        cancelada.linha.cancelada,
        cancelada.cancelada_por,
        cancelada.cancelamento_autorizado_por,
        cancelada.motivo_cancelamento,
    ) == (True, "Dono", None, "Cliente desistiu")


def test_detalhe_mostra_quem_autorizou(sessao, admin, operador, consultor):
    pid = criar_produto(sessao, admin, estoque=Decimal("0"))
    abrir_caixa(sessao, operador)
    dados = NovaVenda(itens=(_p(pid),), forma=DINHEIRO)
    vendida = registrar_venda(sessao, operador, dados, autorizador=admin, confirmar_estoque=True)
    cancelada = registrar_venda(sessao, operador, dados, autorizador=admin, confirmar_estoque=True)
    cancelar_venda(sessao, operador, cancelada, "Erro", autorizador=admin)
    fechar_sessao(sessao, operador, Decimal("0"))
    assert detalhe_venda(sessao, consultor, vendida).autorizado_por == "Dono"
    detalhe = detalhe_venda(sessao, consultor, cancelada)
    assert (detalhe.cancelada_por, detalhe.cancelamento_autorizado_por) == ("Maria", "Dono")


def test_detalhe_de_venda_inexistente(sessao, consultor):
    with pytest.raises(RegistroNaoEncontrado):
        detalhe_venda(sessao, consultor, 999)


def test_listar_sessoes(sessao, admin, operador, consultor, relogio):
    _dia_fechado(sessao, admin, operador, relogio)
    sessoes = listar_sessoes(sessao, consultor, DIA, DIA)
    assert len(sessoes) == 1
    linha = sessoes[0]
    assert (linha.protocolo, linha.aberta_em, linha.fechada_em) == (
        "CX-20260923-1000",
        datetime(2026, 9, 23, 10, 0),
        datetime(2026, 9, 23, 18, 40),
    )
    assert (linha.aberta_por, linha.fechada_por) == ("Maria", "Maria")
    assert (linha.valor_mantido, linha.sangria) == (Decimal("100.00"), Decimal("85.00"))
    assert linha.resumo.total_vendido == Decimal("145.00")
    assert linha.resumo.dinheiro == Decimal("85.00")
    assert linha.resumo.gaveta == Decimal("185.00")
    assert (linha.resumo.canceladas_qtd, linha.resumo.canceladas_bruto) == (1, Decimal("30.00"))
    assert listar_sessoes(sessao, consultor, date(2026, 9, 24), date(2026, 9, 24)) == []


def test_sessao_aberta_nao_aparece_em_sessoes(sessao, operador, consultor):
    abrir_caixa(sessao, operador)
    assert listar_sessoes(sessao, consultor, DIA, DIA) == []


def test_periodo_invertido(sessao, consultor):
    with pytest.raises(ValorInvalido, match="anterior"):
        listar_vendas(sessao, consultor, FiltroHistorico(inicio=DIA, fim=date(2026, 9, 22)))
    with pytest.raises(ValorInvalido, match="anterior"):
        listar_sessoes(sessao, consultor, DIA, date(2026, 9, 22))


def test_exige_modulo_historico(sessao, operador):
    with pytest.raises(PermissaoNegada):
        listar_vendas(sessao, operador, FiltroHistorico(inicio=DIA, fim=DIA))
    with pytest.raises(PermissaoNegada):
        detalhe_venda(sessao, operador, 1)
    with pytest.raises(PermissaoNegada):
        listar_sessoes(sessao, operador, DIA, DIA)
