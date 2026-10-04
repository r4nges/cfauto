"""Importa todos os modelos para registrar as tabelas em Base.metadata."""

from cfauto.auth import models as _auth  # noqa: F401
from cfauto.caixa import models as _caixa  # noqa: F401
from cfauto.clientes import models as _clientes  # noqa: F401
from cfauto.core import models as _core  # noqa: F401
from cfauto.estoque import models as _estoque  # noqa: F401
from cfauto.gestao import models as _gestao  # noqa: F401
from cfauto.licenca import models as _licenca  # noqa: F401
