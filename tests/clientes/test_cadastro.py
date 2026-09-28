from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cfauto.clientes.cadastro import (
    buscar_clientes,
    criar_cliente,
    editar_cliente,
    obter_cliente,
    verificar_duplicados,
)
from cfauto.clientes.models import Cliente, FrequenciaJuros, Sexo
from cfauto.clientes.schemas import DadosCliente, DadosDependente
from cfauto.core.errors import PermissaoNegada, RegistroNaoEncontrado, ValorInvalido
from cfauto.core.models import AuditLog

CPF_VALIDO = "529.982.247-25"


def _dados(nome="Ana Souza", celular="(11) 98765-4321", **campos):
    return DadosCliente(nome=nome, celular=celular, **campos)


def _auditoria(sessao, acao):
    return sessao.scalars(
        select(AuditLog).where(AuditLog.entidade == "cliente", AuditLog.acao == acao)
    ).all()


def test_criar_normaliza_e_gera_codigo(sessao, admin):
    cid = criar_cliente(
        sessao, admin, _dados(nome="  Ana   Souza ", cpf=CPF_VALIDO, email=" ana@x.com ")
    )
    c = sessao.get(Cliente, cid)
    assert (c.codigo, c.nome, c.nome_busca, c.celular, c.cpf, c.email) == (
        "CLI-0001",
        "Ana Souza",
        "ana souza",
        "11987654321",
        "52998224725",
        "ana@x.com",
    )
    assert (c.limite, c.saldo_devedor, c.ativo) == (Decimal("500.00"), Decimal("0.00"), True)
    outro = criar_cliente(sessao, admin, _dados(nome="Bia Lima", celular="11912345678"))
    assert sessao.get(Cliente, outro).codigo == "CLI-0002"


def test_criar_audita(sessao, admin):
    cid = criar_cliente(sessao, admin, _dados(dependentes=(DadosDependente("João Souza"),)))
    (registro,) = _auditoria(sessao, "criar")
    assert registro.entidade_id == str(cid)
    assert registro.antes is None
    assert registro.depois["celular"] == "11987654321"
    assert registro.depois["limite"] == "500.00"
    assert registro.depois["dependentes"] == [{"nome": "João Souza", "parentesco": ""}]


@pytest.mark.parametrize(
    ("campos", "mensagem"),
    [
        ({"nome": "Ana"}, "nome e sobrenome"),
        ({"celular": "98765-4321"}, "DDD"),
        ({"cpf": "529.982.247-26"}, "CPF inválido"),
        ({"email": "ana.com"}, "E-mail"),
        ({"limite": Decimal("-1")}, "limite"),
        ({"nascimento": date(2026, 9, 24)}, "futura"),
        ({"juros_pct": Decimal("-1")}, "juros"),
        ({"dependentes": tuple(DadosDependente(f"Filho {i}") for i in range(5))}, "No máximo 4"),
        (
            {"somente_titular": True, "dependentes": (DadosDependente("Filho Souza"),)},
            "somente titular",
        ),
        ({"dependentes": (DadosDependente("  ", "filho"),)}, "dependente"),
        ({"endereco": "x" * 201}, "Endereço"),
        ({"observacoes": "x" * 501}, "Observações"),
    ],
)
def test_validacoes(sessao, admin, campos, mensagem):
    with pytest.raises(ValorInvalido, match=mensagem):
        criar_cliente(sessao, admin, _dados(**campos))


def test_operador_cria_so_com_limite_padrao(sessao, operador):
    criar_cliente(sessao, operador, _dados())
    with pytest.raises(PermissaoNegada, match="limite"):
        criar_cliente(sessao, operador, _dados(nome="Bia Lima", limite=Decimal("800")))
    with pytest.raises(PermissaoNegada, match="limite"):
        criar_cliente(sessao, operador, _dados(nome="Caio Reis", limite=None))


def test_operador_edita_dados_mas_nao_limite(sessao, admin, operador):
    cid = criar_cliente(sessao, admin, _dados(limite=None))
    # Cliente sem limite: o operador reenvia limite None e não é barrado.
    editar_cliente(sessao, operador, cid, _dados(nome="Ana Souza Lima", limite=None))
    assert sessao.get(Cliente, cid).nome == "Ana Souza Lima"
    with pytest.raises(PermissaoNegada, match="limite"):
        editar_cliente(sessao, operador, cid, _dados(limite=Decimal("300")))


def test_admin_altera_limite(sessao, admin):
    cid = criar_cliente(sessao, admin, _dados())
    editar_cliente(sessao, admin, cid, _dados(limite=Decimal("1200")))
    assert sessao.get(Cliente, cid).limite == Decimal("1200.00")


def test_sem_modulo_clientes(sessao, estoquista):
    with pytest.raises(PermissaoNegada):
        criar_cliente(sessao, estoquista, _dados())
    with pytest.raises(PermissaoNegada):
        buscar_clientes(sessao, estoquista, "")


def test_editar_substitui_dependentes_e_audita(sessao, admin):
    cid = criar_cliente(
        sessao,
        admin,
        _dados(dependentes=(DadosDependente("João Souza", "filho"), DadosDependente("Rita Souza"))),
    )
    editar_cliente(
        sessao, admin, cid, _dados(dependentes=(DadosDependente("Rita Souza", "filha"),))
    )
    ficha = obter_cliente(sessao, admin, cid)
    assert ficha.dados.dependentes == (DadosDependente("Rita Souza", "filha"),)
    (registro,) = _auditoria(sessao, "alterar")
    assert [d["nome"] for d in registro.antes["dependentes"]] == ["João Souza", "Rita Souza"]
    assert registro.depois["dependentes"] == [{"nome": "Rita Souza", "parentesco": "filha"}]


def test_editar_nao_mexe_em_saldo_nem_codigo(sessao, admin):
    cid = criar_cliente(sessao, admin, _dados())
    cliente = sessao.get(Cliente, cid)
    cliente.saldo_devedor = Decimal("40.00")  # simula lançamentos anteriores
    editar_cliente(sessao, admin, cid, _dados(nome="Ana Maria Souza"))
    assert (cliente.codigo, cliente.saldo_devedor) == ("CLI-0001", Decimal("40.00"))


def test_obter_devolve_ficha_completa(sessao, admin):
    cid = criar_cliente(
        sessao,
        admin,
        _dados(
            cpf=CPF_VALIDO,
            email="ana@x.com",
            endereco="Rua A, 10",
            nascimento=date(1990, 5, 1),
            sexo=Sexo.F,
            observacoes="Fiado só até dia 10",
            limite=Decimal("750"),
            juros_dias=15,
            juros_frequencia=FrequenciaJuros.DIARIO,
            juros_pct=Decimal("1.5"),
            juros_mora=True,
            aumento_auto=True,
            aumento_auto_pct=Decimal("10"),
        ),
    )
    ficha = obter_cliente(sessao, admin, cid)
    assert ficha.codigo == "CLI-0001"
    assert ficha.dados == DadosCliente(
        nome="Ana Souza",
        celular="11987654321",
        cpf="52998224725",
        email="ana@x.com",
        endereco="Rua A, 10",
        nascimento=date(1990, 5, 1),
        sexo=Sexo.F,
        observacoes="Fiado só até dia 10",
        limite=Decimal("750.00"),
        juros_dias=15,
        juros_frequencia=FrequenciaJuros.DIARIO,
        juros_pct=Decimal("1.50"),
        juros_mora=True,
        aumento_auto=True,
        aumento_auto_pct=Decimal("10.00"),
    )
    assert (ficha.saldo_devedor, ficha.disponivel, ficha.ativo) == (
        Decimal("0.00"),
        Decimal("750.00"),
        True,
    )
    with pytest.raises(RegistroNaoEncontrado):
        obter_cliente(sessao, admin, 999)


def test_duplicados_por_cpf_ou_celular_ignorando_o_proprio(sessao, admin):
    ana = criar_cliente(sessao, admin, _dados(cpf=CPF_VALIDO))
    criar_cliente(sessao, admin, _dados(nome="Bia Lima", celular="21912345678"))
    por_cpf = verificar_duplicados(
        sessao, admin, _dados(nome="Outra Pessoa", celular="(31) 99999-0000", cpf=CPF_VALIDO)
    )
    assert [r.codigo for r in por_cpf] == ["CLI-0001"]
    por_celular = verificar_duplicados(
        sessao, admin, _dados(nome="Outra Pessoa", celular="21 91234-5678")
    )
    assert [r.codigo for r in por_celular] == ["CLI-0002"]
    assert verificar_duplicados(sessao, admin, _dados(cpf=CPF_VALIDO), ignorar_id=ana) == []


def test_duplicado_nao_impede_salvar(sessao, admin):
    criar_cliente(sessao, admin, _dados())
    criar_cliente(sessao, admin, _dados(nome="Filho Souza"))  # mesmo celular da mãe
    assert len(buscar_clientes(sessao, admin, "")) == 2


def test_duplicados_valida_os_dados_antes(sessao, admin):
    with pytest.raises(ValorInvalido, match="DDD"):
        verificar_duplicados(sessao, admin, _dados(celular="123"))


def test_busca(sessao, admin):
    criar_cliente(sessao, admin, _dados(nome="José Antônio", celular="11987654321", cpf=CPF_VALIDO))
    criar_cliente(sessao, admin, _dados(nome="Maria Silva", celular="21912345678"))

    def codigos(texto):
        return [r.codigo for r in buscar_clientes(sessao, admin, texto)]

    assert codigos("") == ["CLI-0001", "CLI-0002"]
    assert codigos("jose antonio") == ["CLI-0001"]
    assert codigos("SILVA") == ["CLI-0002"]
    assert codigos("cli-0002") == ["CLI-0002"]
    assert codigos("529.982") == ["CLI-0001"]
    assert codigos("91234") == ["CLI-0002"]
    assert codigos("98") == []  # menos de 3 dígitos não busca por CPF/celular
    assert codigos("%") == []
    assert codigos("_") == []
