"""Cliente: cadastro, dependentes, busca e aviso de duplicidade."""

from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from cfauto.clientes.models import LIMITE_PADRAO, MAX_DEPENDENTES, Cliente, ClienteDependente
from cfauto.clientes.schemas import DadosCliente, DadosDependente, FichaCliente, ResumoCliente
from cfauto.clientes.validacao import (
    normalizar_celular,
    normalizar_cpf,
    normalizar_email,
    normalizar_nome,
    so_digitos,
)
from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import PermissaoNegada, RegistroNaoEncontrado, ValorInvalido
from cfauto.core.money import arredondar
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo
from cfauto.core.sequencias import proximo_codigo
from cfauto.core.texto import normalizar_texto

MINIMO_DIGITOS_BUSCA = 3


def _texto(valor: str, rotulo: str, maximo: int) -> str:
    texto = valor.strip()
    if len(texto) > maximo:
        raise ValorInvalido(f"{rotulo}: máximo de {maximo} caracteres.")
    return texto


def _validar(dados: DadosCliente) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Dados digitados → valores das colunas e dependentes (nome, parentesco) normalizados."""
    nome = normalizar_nome(dados.nome)
    valores: dict[str, Any] = {
        "nome": nome,
        "nome_busca": normalizar_texto(nome),
        "celular": normalizar_celular(dados.celular),
        "cpf": normalizar_cpf(dados.cpf),
        "email": normalizar_email(dados.email),
        "endereco": _texto(dados.endereco, "Endereço", 200),
        "nascimento": dados.nascimento,
        "sexo": dados.sexo,
        "observacoes": _texto(dados.observacoes, "Observações", 500),
        "limite": None if dados.limite is None else arredondar(dados.limite),
        "somente_titular": dados.somente_titular,
        "aumento_auto": dados.aumento_auto,
        "aumento_auto_pct": arredondar(dados.aumento_auto_pct),
        "juros_dias": dados.juros_dias,
        "juros_frequencia": dados.juros_frequencia,
        "juros_pct": arredondar(dados.juros_pct),
        "juros_mora": dados.juros_mora,
    }
    if valores["limite"] is not None and valores["limite"] < 0:
        raise ValorInvalido("O limite não pode ser negativo.")
    if dados.nascimento is not None and dados.nascimento > clock.hoje():
        raise ValorInvalido("A data de nascimento não pode ser futura.")
    if dados.juros_dias < 0 or valores["juros_pct"] < 0 or valores["aumento_auto_pct"] < 0:
        raise ValorInvalido("Os parâmetros de juros não podem ser negativos.")
    if len(dados.dependentes) > MAX_DEPENDENTES:
        raise ValorInvalido(f"No máximo {MAX_DEPENDENTES} dependentes.")
    if dados.somente_titular and dados.dependentes:
        raise ValorInvalido("Cliente marcado como somente titular não pode ter dependentes.")
    dependentes: list[tuple[str, str]] = []
    for dependente in dados.dependentes:
        nome_dependente = " ".join(_texto(dependente.nome, "Nome do dependente", 120).split())
        if not nome_dependente:
            raise ValorInvalido("Nome do dependente obrigatório.")
        dependentes.append((nome_dependente, _texto(dependente.parentesco, "Parentesco", 40)))
    return valores, dependentes


def _snapshot(c: Cliente) -> dict[str, Any]:
    return {
        "codigo": c.codigo,
        "nome": c.nome,
        "celular": c.celular,
        "cpf": c.cpf,
        "email": c.email,
        "endereco": c.endereco,
        "nascimento": c.nascimento,
        "sexo": c.sexo,
        "observacoes": c.observacoes,
        "limite": c.limite,
        "saldo_devedor": c.saldo_devedor,
        "somente_titular": c.somente_titular,
        "dependentes": [{"nome": d.nome, "parentesco": d.parentesco} for d in c.dependentes],
        "aumento_auto": c.aumento_auto,
        "aumento_auto_pct": c.aumento_auto_pct,
        "juros_dias": c.juros_dias,
        "juros_frequencia": c.juros_frequencia,
        "juros_pct": c.juros_pct,
        "juros_mora": c.juros_mora,
        "ativo": c.ativo,
    }


def _exigir_admin_para_limite(ator: Ator) -> None:
    if not ator.admin:
        raise PermissaoNegada("Só administradores alteram o limite de crédito.")


def _novos_dependentes(dependentes: list[tuple[str, str]]) -> list[ClienteDependente]:
    return [ClienteDependente(nome=nome, parentesco=parentesco) for nome, parentesco in dependentes]


def carregar_cliente(s: Session, cliente_id: int) -> Cliente:
    cliente = s.get(Cliente, cliente_id)
    if cliente is None:
        raise RegistroNaoEncontrado("Cliente não encontrado.")
    return cliente


def resumo_cliente(c: Cliente) -> ResumoCliente:
    return ResumoCliente(
        id=c.id,
        codigo=c.codigo,
        nome=c.nome,
        celular=c.celular,
        cpf=c.cpf,
        saldo_devedor=c.saldo_devedor,
        limite=c.limite,
        disponivel=c.disponivel,
        ativo=c.ativo,
    )


def criar_cliente(s: Session, ator: Ator, dados: DadosCliente) -> int:
    exigir_modulo(ator, Modulo.CLIENTES)
    valores, dependentes = _validar(dados)
    if valores["limite"] != LIMITE_PADRAO:
        _exigir_admin_para_limite(ator)
    cliente = Cliente(
        codigo=proximo_codigo(s, "cliente", prefixo="CLI-", digitos=4),
        saldo_devedor=Decimal("0.00"),
        ativo=True,
        **valores,
    )
    cliente.dependentes = _novos_dependentes(dependentes)
    s.add(cliente)
    s.flush()
    registrar(s, ator.id, "criar", "cliente", cliente.id, None, _snapshot(cliente))
    return cliente.id


def editar_cliente(s: Session, ator: Ator, cliente_id: int, dados: DadosCliente) -> None:
    """Nunca altera código nem saldo devedor; a lista de dependentes é substituída inteira."""
    exigir_modulo(ator, Modulo.CLIENTES)
    cliente = carregar_cliente(s, cliente_id)
    valores, dependentes = _validar(dados)
    if valores["limite"] != cliente.limite:
        _exigir_admin_para_limite(ator)
    antes = _snapshot(cliente)
    for campo, valor in valores.items():
        setattr(cliente, campo, valor)
    cliente.dependentes = _novos_dependentes(dependentes)
    s.flush()
    registrar(s, ator.id, "alterar", "cliente", cliente.id, antes, _snapshot(cliente))


def verificar_duplicados(
    s: Session, ator: Ator, dados: DadosCliente, ignorar_id: int | None = None
) -> list[ResumoCliente]:
    """Clientes com o mesmo CPF ou celular. Valida os dados antes, para o erro de digitação
    aparecer primeiro."""
    exigir_modulo(ator, Modulo.CLIENTES)
    valores, _ = _validar(dados)
    condicoes: list[ColumnElement[bool]] = [Cliente.celular == valores["celular"]]
    if valores["cpf"] is not None:
        condicoes.append(Cliente.cpf == valores["cpf"])
    consulta = select(Cliente).where(or_(*condicoes)).order_by(Cliente.id)
    if ignorar_id is not None:
        consulta = consulta.where(Cliente.id != ignorar_id)
    return [resumo_cliente(c) for c in s.scalars(consulta)]


def buscar_clientes(
    s: Session, ator: Ator, texto: str = "", *, incluir_inativos: bool = False
) -> list[ResumoCliente]:
    """Por nome (sem acento), código, ou dígitos de CPF/celular (a partir de 3 dígitos)."""
    exigir_modulo(ator, Modulo.CLIENTES)
    consulta = select(Cliente).order_by(Cliente.nome_busca, Cliente.id)
    if not incluir_inativos:
        consulta = consulta.where(Cliente.ativo.is_(True))
    termo = normalizar_texto(texto)
    if termo:
        condicoes: list[ColumnElement[bool]] = [
            Cliente.nome_busca.contains(termo, autoescape=True),
            Cliente.codigo.contains(texto.strip().upper(), autoescape=True),
        ]
        digitos = so_digitos(texto)
        if len(digitos) >= MINIMO_DIGITOS_BUSCA:
            condicoes.append(Cliente.cpf.contains(digitos))
            condicoes.append(Cliente.celular.contains(digitos))
        consulta = consulta.where(or_(*condicoes))
    return [resumo_cliente(c) for c in s.scalars(consulta)]


def obter_cliente(s: Session, ator: Ator, cliente_id: int) -> FichaCliente:
    exigir_modulo(ator, Modulo.CLIENTES)
    c = carregar_cliente(s, cliente_id)
    dados = DadosCliente(
        nome=c.nome,
        celular=c.celular,
        cpf=c.cpf or "",
        email=c.email or "",
        endereco=c.endereco,
        nascimento=c.nascimento,
        sexo=c.sexo,
        observacoes=c.observacoes,
        limite=c.limite,
        somente_titular=c.somente_titular,
        dependentes=tuple(DadosDependente(d.nome, d.parentesco) for d in c.dependentes),
        aumento_auto=c.aumento_auto,
        aumento_auto_pct=c.aumento_auto_pct,
        juros_dias=c.juros_dias,
        juros_frequencia=c.juros_frequencia,
        juros_pct=c.juros_pct,
        juros_mora=c.juros_mora,
    )
    return FichaCliente(
        id=c.id,
        codigo=c.codigo,
        dados=dados,
        saldo_devedor=c.saldo_devedor,
        disponivel=c.disponivel,
        ativo=c.ativo,
    )
