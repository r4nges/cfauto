from datetime import date

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cfauto.auth.service import autenticar, existe_usuario
from cfauto.core import config
from cfauto.core.db import transacao
from cfauto.core.errors import LicencaInvalida
from cfauto.licenca.formato import PayloadLicenca, assinar
from cfauto.licenca.service import avaliar
from cfauto.sistema.primeira_execucao import DadosPrimeiraExecucao, concluir


def _dados(chave):
    return DadosPrimeiraExecucao(
        nome="Dono",
        login="dono",
        senha="segredo1",
        chave_licenca=chave,
        empresa_nome="Loja X",
        empresa_cnpj="12.345.678/0001-90",
    )


def test_concluir(fabrica, relogio):
    privada = Ed25519PrivateKey.generate()
    chave = assinar(PayloadLicenca("Loja X", date(2026, 9, 1), date(2027, 9, 1)), privada)
    with transacao(fabrica) as s:
        ator = concluir(s, _dados(chave), publica=privada.public_key())
    assert ator.admin
    with transacao(fabrica) as s:
        assert autenticar(s, "dono", "segredo1").id == ator.id
        assert avaliar(s, publica=privada.public_key()).valida
        assert config.obter(s, "empresa.nome") == "Loja X"
        assert config.obter(s, "empresa.cnpj") == "12.345.678/0001-90"


def test_licenca_invalida_desfaz_tudo(fabrica, relogio):
    with pytest.raises(LicencaInvalida), transacao(fabrica) as s:
        concluir(s, _dados("lixo"), publica=Ed25519PrivateKey.generate().public_key())
    with transacao(fabrica) as s:
        assert not existe_usuario(s)
