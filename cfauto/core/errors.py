"""Exceções de domínio. A mensagem de cada uma é exibível ao usuário."""

from datetime import datetime


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
    pass


class ClienteComSaldo(ErroDominio):
    pass


class ClienteComHistorico(ErroDominio):
    pass
