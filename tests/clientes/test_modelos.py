from decimal import Decimal

from cfauto.clientes.models import Cliente, ClienteDependente, FrequenciaJuros


def _cliente(**campos):
    base = {
        "codigo": "CLI-0001",
        "nome": "Ana Souza",
        "nome_busca": "ana souza",
        "celular": "11987654321",
    }
    base.update(campos)
    return Cliente(**base)


def test_padroes_gravados(sessao, relogio):
    cliente = _cliente()
    sessao.add(cliente)
    sessao.flush()
    sessao.expire(cliente)
    assert cliente.saldo_devedor == Decimal("0.00")
    assert cliente.limite is None
    assert (cliente.endereco, cliente.observacoes) == ("", "")
    assert (cliente.somente_titular, cliente.aumento_auto, cliente.juros_mora) == (
        False,
        False,
        False,
    )
    assert cliente.aumento_auto_pct == Decimal("5.00")
    assert (cliente.juros_dias, cliente.juros_frequencia) == (30, FrequenciaJuros.MENSAL)
    assert cliente.juros_pct == Decimal("2.00")
    assert cliente.ativo is True


def test_disponivel():
    assert _cliente(limite=None, saldo_devedor=Decimal("80")).disponivel is None
    assert _cliente(limite=Decimal("500"), saldo_devedor=Decimal("120")).disponivel == Decimal(
        "380"
    )
    # Crédito a favor aumenta o disponível.
    assert _cliente(limite=Decimal("500"), saldo_devedor=Decimal("-50")).disponivel == Decimal(
        "550"
    )


def test_dependentes_saem_junto_com_o_cliente(sessao, relogio):
    cliente = _cliente()
    cliente.dependentes = [ClienteDependente(nome="João Souza", parentesco="filho")]
    sessao.add(cliente)
    sessao.flush()
    sessao.delete(cliente)
    sessao.flush()
    assert sessao.query(ClienteDependente).count() == 0
