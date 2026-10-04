"""Razão do cliente: única porta de alteração do saldo devedor, lançamento manual e extrato."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.auth.models import Usuario
from cfauto.clientes.cadastro import carregar_cliente, resumo_cliente
from cfauto.clientes.models import (
    MOTIVOS_MANUAIS,
    Cliente,
    ClienteLancamento,
    MotivoLancamento,
    TipoLancamento,
)
from cfauto.clientes.schemas import Extrato, LinhaLancamento
from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import ValorInvalido
from cfauto.core.money import arredondar
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo

TAMANHO_OBSERVACAO = 200


def saldo_apos(saldo: Decimal, tipo: TipoLancamento, valor: Decimal) -> Decimal:
    """DEBITO aumenta a dívida; CREDITO abate (pode ficar negativo: crédito a favor)."""
    return saldo + valor if tipo == TipoLancamento.DEBITO else saldo - valor


def lancar(
    s: Session,
    ator: Ator,
    cliente: Cliente,
    tipo: TipoLancamento,
    valor: Decimal,
    motivo: MotivoLancamento,
    observacao: str = "",
    *,
    venda_id: int | None = None,
) -> ClienteLancamento:
    """Única porta de alteração de `saldo_devedor`. Não checa permissão, limite nem situação
    do cliente: quem chama decide. `venda_id` liga o lançamento automático à venda do caixa."""
    valor = arredondar(valor)
    if valor <= 0:
        raise ValorInvalido("O valor do lançamento deve ser maior que zero.")
    observacao = observacao.strip()
    if len(observacao) > TAMANHO_OBSERVACAO:
        raise ValorInvalido(f"Observação: máximo de {TAMANHO_OBSERVACAO} caracteres.")
    if motivo == MotivoLancamento.CORRECAO and not observacao:
        raise ValorInvalido("Informe na observação o motivo da correção.")
    antes = cliente.saldo_devedor
    cliente.saldo_devedor = saldo_apos(antes, tipo, valor)
    lancamento = ClienteLancamento(
        cliente_id=cliente.id,
        data_hora=clock.agora(),
        tipo=tipo,
        valor=valor,
        saldo_apos=cliente.saldo_devedor,
        motivo=motivo,
        observacao=observacao,
        usuario_id=ator.id,
        venda_id=venda_id,
    )
    s.add(lancamento)
    s.flush()
    depois: dict[str, object] = {
        "saldo_devedor": cliente.saldo_devedor,
        "tipo": tipo,
        "valor": valor,
        "motivo": motivo,
        "lancamento_id": lancamento.id,
    }
    if venda_id is not None:
        depois["venda_id"] = venda_id
    registrar(s, ator.id, "lancamento", "cliente", cliente.id, {"saldo_devedor": antes}, depois)
    return lancamento


def _linha(lancamento: ClienteLancamento, usuario: str) -> LinhaLancamento:
    return LinhaLancamento(
        id=lancamento.id,
        data_hora=lancamento.data_hora,
        tipo=lancamento.tipo,
        valor=lancamento.valor,
        saldo_apos=lancamento.saldo_apos,
        motivo=lancamento.motivo,
        observacao=lancamento.observacao,
        usuario=usuario,
    )


def lancar_manual(
    s: Session,
    ator: Ator,
    cliente_id: int,
    tipo: TipoLancamento,
    valor: Decimal,
    motivo: MotivoLancamento,
    observacao: str = "",
) -> LinhaLancamento:
    exigir_modulo(ator, Modulo.CLIENTES)
    if motivo not in MOTIVOS_MANUAIS:
        raise ValorInvalido("Motivo reservado aos lançamentos automáticos do caixa.")
    cliente = carregar_cliente(s, cliente_id)
    if not cliente.ativo:
        raise ValorInvalido("Cliente inativo: reative antes de lançar.")
    return _linha(lancar(s, ator, cliente, tipo, valor, motivo, observacao), ator.nome)


def extrato(s: Session, ator: Ator, cliente_id: int, inicio: date, fim: date) -> Extrato:
    """Lançamentos de `inicio` 00:00 até o fim do dia `fim`, com o saldo anterior ao período."""
    exigir_modulo(ator, Modulo.CLIENTES)
    if fim < inicio:
        raise ValorInvalido("A data final é anterior à inicial.")
    cliente = carregar_cliente(s, cliente_id)
    comeco = datetime.combine(inicio, time.min)
    depois_do_fim = datetime.combine(fim + timedelta(days=1), time.min)
    do_cliente = ClienteLancamento.cliente_id == cliente.id
    anterior = s.scalar(
        select(ClienteLancamento.saldo_apos)
        .where(do_cliente, ClienteLancamento.data_hora < comeco)
        .order_by(ClienteLancamento.data_hora.desc(), ClienteLancamento.id.desc())
        .limit(1)
    )
    saldo_anterior = anterior if anterior is not None else Decimal("0.00")
    consulta = (
        select(ClienteLancamento, Usuario.nome.label("usuario"))
        .join(Usuario, Usuario.id == ClienteLancamento.usuario_id)
        .where(
            do_cliente,
            ClienteLancamento.data_hora >= comeco,
            ClienteLancamento.data_hora < depois_do_fim,
        )
        .order_by(ClienteLancamento.data_hora, ClienteLancamento.id)
    )
    linhas = tuple(_linha(row.ClienteLancamento, row.usuario) for row in s.execute(consulta))
    return Extrato(
        cliente=resumo_cliente(cliente),
        inicio=inicio,
        fim=fim,
        saldo_anterior=saldo_anterior,
        linhas=linhas,
        saldo_final=linhas[-1].saldo_apos if linhas else saldo_anterior,
    )
