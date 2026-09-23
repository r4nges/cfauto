from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cfauto.core.db import criar_engine, criar_fabrica, transacao
from cfauto.core.tipos import Dinheiro, Quantidade


class _BaseTeste(DeclarativeBase):
    pass


class _Item(_BaseTeste):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    preco: Mapped[Decimal] = mapped_column(Dinheiro())
    qtd: Mapped[Decimal] = mapped_column(Quantidade())


@pytest.fixture
def fab(tmp_path):
    engine = criar_engine(f"sqlite:///{tmp_path / 'x.db'}")
    _BaseTeste.metadata.create_all(engine)
    yield criar_fabrica(engine)
    engine.dispose()


def test_decimal_escalado_ida_e_volta(fab):
    with transacao(fab) as s:
        s.add(_Item(id=1, preco=Decimal("10.10"), qtd=Decimal("1.5")))
    with transacao(fab) as s:
        item = s.get(_Item, 1)
        assert item is not None
        assert item.preco == Decimal("10.10")
        assert str(item.preco) == "10.10"
        assert item.qtd == Decimal("1.500")
        bruto = s.connection().exec_driver_sql("select preco, qtd from item").one()
        assert tuple(bruto) == (1010, 1500)


def test_decimal_escalado_arredonda_meio_para_cima(fab):
    with transacao(fab) as s:
        s.add(_Item(id=1, preco=Decimal("0.005"), qtd=Decimal("0.0005")))
    with transacao(fab) as s:
        item = s.get(_Item, 1)
        assert item is not None
        assert item.preco == Decimal("0.01")
        assert item.qtd == Decimal("0.001")


def test_soma_em_sql_exata(fab):
    with transacao(fab) as s:
        for i in range(1, 4):
            s.add(_Item(id=i, preco=Decimal("0.10"), qtd=Decimal("1")))
    with transacao(fab) as s:
        assert s.scalar(select(func.sum(_Item.preco))) == Decimal("0.30")


def test_transacao_faz_rollback_em_erro(fab):
    with pytest.raises(RuntimeError), transacao(fab) as s:
        s.add(_Item(id=1, preco=Decimal("1"), qtd=Decimal("1")))
        s.flush()
        raise RuntimeError("falha")
    with transacao(fab) as s:
        assert s.get(_Item, 1) is None


def test_foreign_keys_ativas(fab):
    with transacao(fab) as s:
        assert s.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
