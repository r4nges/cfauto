from cfauto.core.db import transacao
from cfauto.core.models import Sequencia
from cfauto.core.sequencias import proximo_codigo


def test_codigos_consecutivos_e_sequencias_independentes(sessao):
    assert proximo_codigo(sessao, "produto", digitos=4) == "0001"
    assert proximo_codigo(sessao, "produto", digitos=4) == "0002"
    assert proximo_codigo(sessao, "servico", prefixo="SERV-", digitos=3) == "SERV-001"


def test_passa_do_limite_de_digitos(sessao):
    sessao.add(Sequencia(nome="produto", ultimo=9999))
    sessao.flush()
    assert proximo_codigo(sessao, "produto", digitos=4) == "10000"


def test_numero_persiste_entre_transacoes(fabrica):
    with transacao(fabrica) as s:
        proximo_codigo(s, "bem", prefixo="BEM-", digitos=3)
    with transacao(fabrica) as s:
        assert proximo_codigo(s, "bem", prefixo="BEM-", digitos=3) == "BEM-002"
