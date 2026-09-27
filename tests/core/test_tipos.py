from decimal import Decimal
from enum import StrEnum

import pytest
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cfauto.core.db import criar_engine, criar_fabrica, transacao
from cfauto.core.tipos import Custo, EnumTexto


class _Cor(StrEnum):
    AZUL = "AZUL"
    VERDE = "VERDE"


class _BaseTeste(DeclarativeBase):
    pass


class _Coisa(_BaseTeste):
    __tablename__ = "coisa"
    id: Mapped[int] = mapped_column(primary_key=True)
    custo: Mapped[Decimal] = mapped_column(Custo())
    cor: Mapped[_Cor] = mapped_column(EnumTexto(_Cor))


@pytest.fixture
def fab(tmp_path):
    engine = criar_engine(f"sqlite:///{tmp_path / 'x.db'}")
    _BaseTeste.metadata.create_all(engine)
    yield criar_fabrica(engine)
    engine.dispose()


def test_custo_guarda_quatro_casas(fab):
    with transacao(fab) as s:
        s.add(_Coisa(id=1, custo=Decimal("0.035"), cor=_Cor.AZUL))
    with transacao(fab) as s:
        coisa = s.get(_Coisa, 1)
        assert str(coisa.custo) == "0.0350"
        bruto = s.connection().exec_driver_sql("select custo, cor from coisa").one()
        assert tuple(bruto) == (350, "AZUL")


def test_enum_texto_volta_como_enum(fab):
    with transacao(fab) as s:
        s.add(_Coisa(id=1, custo=Decimal("1"), cor="VERDE"))
    with transacao(fab) as s:
        assert s.get(_Coisa, 1).cor is _Cor.VERDE


def test_enum_texto_rejeita_valor_desconhecido(fab):
    with pytest.raises(StatementError, match="ROXO"), transacao(fab) as s:
        s.add(_Coisa(id=1, custo=Decimal("1"), cor="ROXO"))
