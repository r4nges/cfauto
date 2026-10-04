"""Exceções de domínio. A mensagem de cada uma é exibível ao usuário."""

from datetime import datetime
from decimal import Decimal


class ErroDominio(Exception):
    pass


class ValorInvalido(ErroDominio):
    pass


class DataInvalida(ValorInvalido):
    pass


class RegistroNaoEncontrado(ErroDominio):
    pass


class PermissaoNegada(ErroDominio):
    pass


class CredenciaisInvalidas(ErroDominio):
    def __init__(self) -> None:
        super().__init__("Login ou senha inválidos.")


class UsuarioBloqueado(ErroDominio):
    def __init__(self, ate: datetime) -> None:
        super().__init__(f"Usuário bloqueado até {ate:%H:%M}.")
        self.ate = ate


class LoginDuplicado(ErroDominio):
    pass


class LicencaInvalida(ErroDominio):
    pass


class LicencaExpirada(LicencaInvalida):
    pass


class EanDuplicado(ValorInvalido):
    pass


class XmlInvalido(ValorInvalido):
    pass


class NotaJaImportada(ErroDominio):
    pass


class EstoqueInsuficiente(ErroDominio):
    def __init__(self, mensagem: str, faltas: tuple[str, ...] = ()) -> None:
        super().__init__(mensagem)
        # Uma linha por produto em falta, ex.: "0001 Óleo 5W30: estoque 1, pedido 3".
        self.faltas = faltas


class ClienteComSaldo(ErroDominio):
    pass


class ClienteComHistorico(ErroDominio):
    pass


class SessaoFechada(ErroDominio):
    pass


class SessaoJaAberta(ErroDominio):
    pass


class LimiteExcedido(ErroDominio):
    """A mensagem já vem formatada por quem levanta (este módulo não importa core.money)."""

    def __init__(self, mensagem: str, disponivel: Decimal, excesso: Decimal) -> None:
        super().__init__(mensagem)
        self.disponivel = disponivel
        self.excesso = excesso
