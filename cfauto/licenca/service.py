from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy.orm import Session

from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import LicencaExpirada, LicencaInvalida
from cfauto.licenca.chave_publica import CHAVE_PUBLICA_HEX
from cfauto.licenca.formato import PayloadLicenca, carregar_publica_hex, verificar_assinatura
from cfauto.licenca.maquina import id_maquina
from cfauto.licenca.models import LicencaEstado

TOLERANCIA_RELOGIO = timedelta(days=1)


class StatusLicenca(StrEnum):
    VALIDA = "VALIDA"
    AUSENTE = "AUSENTE"
    INVALIDA = "INVALIDA"
    EXPIRADA = "EXPIRADA"
    RELOGIO = "RELOGIO"


@dataclass(frozen=True)
class EstadoLicenca:
    status: StatusLicenca
    payload: PayloadLicenca | None = None
    dias_restantes: int | None = None

    @property
    def valida(self) -> bool:
        return self.status is StatusLicenca.VALIDA

    @property
    def mensagem(self) -> str:
        if self.status is StatusLicenca.VALIDA and self.payload:
            return f"Licença válida até {self.payload.expira:%d/%m/%Y}."
        if self.status is StatusLicenca.EXPIRADA and self.payload:
            return f"A licença expirou em {self.payload.expira:%d/%m/%Y}."
        if self.status is StatusLicenca.RELOGIO:
            return (
                "Relógio do sistema inconsistente. Corrija a data do Windows e abra o CFAUTO "
                "novamente."
            )
        if self.status is StatusLicenca.INVALIDA:
            return "Licença inválida."
        return "Nenhuma licença instalada."


def _publica(publica: Ed25519PublicKey | None) -> Ed25519PublicKey:
    return publica or carregar_publica_hex(CHAVE_PUBLICA_HEX)


def _conferir_maquina(payload: PayloadLicenca, maquina_atual: str | None) -> None:
    if payload.maquina and payload.maquina != (maquina_atual or id_maquina()):
        raise LicencaInvalida("Esta licença foi emitida para outra máquina.")


def _linha(s: Session) -> LicencaEstado:
    linha = s.get(LicencaEstado, 1)
    if linha is None:
        linha = LicencaEstado(id=1)
        s.add(linha)
        s.flush()
    return linha


def validar(
    chave: str, *, publica: Ed25519PublicKey | None = None, maquina_atual: str | None = None
) -> PayloadLicenca:
    payload = verificar_assinatura(chave, _publica(publica))
    _conferir_maquina(payload, maquina_atual)
    if payload.expira < clock.hoje():
        raise LicencaExpirada(f"A licença expirou em {payload.expira:%d/%m/%Y}.")
    return payload


def instalar(
    s: Session,
    chave: str,
    *,
    publica: Ed25519PublicKey | None = None,
    maquina_atual: str | None = None,
) -> EstadoLicenca:
    payload = validar(chave, publica=publica, maquina_atual=maquina_atual)
    linha = _linha(s)
    linha.chave = chave.strip()
    s.flush()
    registrar(
        s,
        None,
        "instalar",
        "licenca",
        payload.cliente,
        None,
        {"cliente": payload.cliente, "expira": payload.expira},
    )
    return avaliar(s, publica=publica, maquina_atual=maquina_atual)


def avaliar(
    s: Session, *, publica: Ed25519PublicKey | None = None, maquina_atual: str | None = None
) -> EstadoLicenca:
    linha = _linha(s)
    if not linha.chave:
        return EstadoLicenca(StatusLicenca.AUSENTE)
    hoje = clock.hoje()
    if linha.ultima_data_vista and hoje < linha.ultima_data_vista - TOLERANCIA_RELOGIO:
        return EstadoLicenca(StatusLicenca.RELOGIO)
    try:
        payload = verificar_assinatura(linha.chave, _publica(publica))
        _conferir_maquina(payload, maquina_atual)
    except LicencaInvalida:
        return EstadoLicenca(StatusLicenca.INVALIDA)
    if linha.ultima_data_vista is None or hoje > linha.ultima_data_vista:
        linha.ultima_data_vista = hoje
        s.flush()
    if payload.expira < hoje:
        return EstadoLicenca(StatusLicenca.EXPIRADA, payload)
    return EstadoLicenca(StatusLicenca.VALIDA, payload, (payload.expira - hoje).days)
