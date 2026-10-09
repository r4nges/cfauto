from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from PySide6.QtWidgets import (
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
    QWizard,
    QWizardPage,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.auth.service import SENHA_MINIMA
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.permissoes import Ator
from cfauto.licenca.maquina import id_maquina
from cfauto.licenca.service import validar
from cfauto.sistema.primeira_execucao import DadosPrimeiraExecucao, concluir
from cfauto.ui.comum import mostrar_erro
from cfauto.ui.tema import pixmap_marca


class _PaginaAdmin(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Administrador")
        self.setSubTitle("Crie o usuário administrador do sistema.")
        self.nome, self.login = QLineEdit(), QLineEdit()
        self.senha, self.confirmacao = QLineEdit(), QLineEdit()
        for campo in (self.senha, self.confirmacao):
            campo.setEchoMode(QLineEdit.EchoMode.Password)
        form = QFormLayout(self)
        form.addRow("Nome", self.nome)
        form.addRow("Login", self.login)
        form.addRow("Senha", self.senha)
        form.addRow("Confirmar senha", self.confirmacao)

    def validatePage(self) -> bool:  # noqa: N802 - API do Qt
        if not self.nome.text().strip() or not self.login.text().strip():
            mostrar_erro(self, ErroDominio("Informe nome e login."))
            return False
        if len(self.senha.text()) < SENHA_MINIMA:
            mostrar_erro(self, ErroDominio(f"A senha deve ter ao menos {SENHA_MINIMA} caracteres."))
            return False
        if self.senha.text() != self.confirmacao.text():
            mostrar_erro(self, ErroDominio("As senhas não conferem."))
            return False
        return True


class _PaginaLicenca(QWizardPage):
    def __init__(self, publica: Ed25519PublicKey | None) -> None:
        super().__init__()
        self._publica = publica
        self.setTitle("Licença")
        self.setSubTitle("Informe o ID abaixo ao fornecedor e cole a chave recebida.")
        maquina = QLineEdit(id_maquina())
        maquina.setReadOnly(True)
        self.chave = QPlainTextEdit()
        form = QFormLayout(self)
        form.addRow("ID desta máquina", maquina)
        form.addRow("Chave", self.chave)

    def validatePage(self) -> bool:  # noqa: N802 - API do Qt
        try:
            validar(self.chave.toPlainText(), publica=self._publica)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return False
        return True


class _PaginaEmpresa(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Empresa")
        self.nome, self.cnpj = QLineEdit(), QLineEdit()
        form = QFormLayout(self)
        form.addRow("Nome da empresa", self.nome)
        form.addRow("CNPJ (opcional)", self.cnpj)


LARGURA_JANELA = 640
ALTURA_JANELA = 440
LARGURA_MARCA = 210
ALTURA_MARCA = 314  # altura útil entre o cabeçalho e a barra de botões (conferida no Windows)


class AssistentePrimeiraExecucao(QWizard):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        *,
        publica: Ed25519PublicKey | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._publica = publica
        self.ator: Ator | None = None
        self.setWindowTitle("CFAUTO — Primeira execução")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setFixedSize(LARGURA_JANELA, ALTURA_JANELA)
        self.setPixmap(
            QWizard.WizardPixmap.WatermarkPixmap, pixmap_marca(LARGURA_MARCA, ALTURA_MARCA)
        )
        self._admin = _PaginaAdmin()
        self._licenca = _PaginaLicenca(publica)
        self._empresa = _PaginaEmpresa()
        for pagina in (self._admin, self._licenca, self._empresa):
            self.addPage(pagina)

    def accept(self) -> None:
        dados = DadosPrimeiraExecucao(
            nome=self._admin.nome.text(),
            login=self._admin.login.text(),
            senha=self._admin.senha.text(),
            chave_licenca=self._licenca.chave.toPlainText(),
            empresa_nome=self._empresa.nome.text(),
            empresa_cnpj=self._empresa.cnpj.text(),
        )
        try:
            with transacao(self._fabrica) as s:
                self.ator = concluir(s, dados, publica=self._publica)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        super().accept()
