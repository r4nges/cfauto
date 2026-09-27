from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from cfauto.core.jsonutil import para_json


class Cor(StrEnum):
    AZUL = "AZUL"


def test_para_json_converte_tipos():
    valor = {
        "preco": Decimal("10.50"),
        "dia": date(2026, 9, 23),
        "quando": datetime(2026, 9, 23, 10, 0),
        "cor": Cor.AZUL,
        "tags": frozenset({"b", "a"}),
        "lista": [Decimal("1"), None, True, 3],
    }
    assert para_json(valor) == {
        "preco": "10.50",
        "dia": "2026-09-23",
        "quando": "2026-09-23T10:00:00",
        "cor": "AZUL",
        "tags": ["a", "b"],
        "lista": ["1", None, True, 3],
    }
