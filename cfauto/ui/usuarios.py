from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.auth.models import Usuario
from cfauto.auth.service import (
    AlteracaoUsuario,
    NovoUsuario,
    alterar_senha,
    atualizar_usuario,
    criar_usuario,
    listar_usuarios,
)
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio
from cfauto.core.permissoes import TITULOS, Ator, Modulo
from cfauto.ui.comum import mostrar_erro

_MODULOS_EDITAVEIS = [m for m in Modulo if m is not Modulo.USUARIOS]
_COLUNAS = ["Nome", "Login", "Função", "Admin", "Módulos", "Ativo"]


class DialogoUsuario(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        usuario: Usuario | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._usuario = usuario
        self.setWindowTitle("Novo usuário" if usuario is None else f"Editar {usuario.nome}")

        self.nome = QLineEdit(usuario.nome if usuario else "")
        self.login = QLineEdit(usuario.login if usuario else "")
        self.login.setEnabled(usuario is None)
        self.funcao = QLineEdit(usuario.funcao if usuario else "")
        self.senha = QLineEdit()
        self.senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin = QCheckBox("Administrador")
        self.admin.setChecked(bool(usuario and usuario.admin))
        self.ativo = QCheckBox("Ativo")
        self.ativo.setChecked(usuario.ativo if usuario else True)

        form = QFormLayout()
        form.addRow("Nome", self.nome)
        form.addRow("Login", self.login)
        form.addRow("Função", self.funcao)
        if usuario is None:
            form.addRow("Senha", self.senha)
        form.addRow("", self.admin)
        form.addRow("", self.ativo)

        grupo = QGroupBox("Módulos")
        grade = QGridLayout(grupo)
        atuais = set(usuario.modulos) if usuario else set()
        self.caixas_modulo: dict[Modulo, QCheckBox] = {}
        for i, modulo in enumerate(_MODULOS_EDITAVEIS):
            caixa = QCheckBox(TITULOS[modulo])
            caixa.setChecked(modulo.value in atuais)
            self.caixas_modulo[modulo] = caixa
            grade.addWidget(caixa, i // 2, i % 2)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.salvar)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(grupo)
        layout.addWidget(botoes)

    def _modulos(self) -> frozenset[Modulo]:
        return frozenset(m for m, caixa in self.caixas_modulo.items() if caixa.isChecked())

    def salvar(self) -> None:
        try:
            with transacao(self._fabrica) as s:
                if self._usuario is None:
                    criar_usuario(
                        s,
                        self._ator,
                        NovoUsuario(
                            nome=self.nome.text(),
                            login=self.login.text(),
                            senha=self.senha.text(),
                            admin=self.admin.isChecked(),
                            modulos=self._modulos(),
                            funcao=self.funcao.text(),
                        ),
                    )
                else:
                    atualizar_usuario(
                        s,
                        self._ator,
                        self._usuario.id,
                        AlteracaoUsuario(
                            nome=self.nome.text(),
                            funcao=self.funcao.text(),
                            admin=self.admin.isChecked(),
                            modulos=self._modulos(),
                            ativo=self.ativo.isChecked(),
                        ),
                    )
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.accept()


class TelaUsuarios(QWidget):
    def __init__(self, fabrica: sessionmaker[Session], ator: Ator) -> None:
        super().__init__()
        self._fabrica = fabrica
        self._ator = ator
        self._usuarios: list[Usuario] = []

        self.tabela = QTableWidget(0, len(_COLUNAS))
        self.tabela.setHorizontalHeaderLabels(_COLUNAS)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.horizontalHeader().setStretchLastSection(True)

        novo = QPushButton("Novo")
        novo.clicked.connect(self._novo)
        editar = QPushButton("Editar")
        editar.clicked.connect(self._editar)
        senha = QPushButton("Alterar senha")
        senha.clicked.connect(self._alterar_senha)
        botoes = QHBoxLayout()
        for botao in (novo, editar, senha):
            botoes.addWidget(botao)
        botoes.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(botoes)
        layout.addWidget(self.tabela)
        self.recarregar()

    def recarregar(self) -> None:
        with transacao(self._fabrica) as s:
            self._usuarios = listar_usuarios(s, self._ator)
        self.tabela.setRowCount(len(self._usuarios))
        for linha, u in enumerate(self._usuarios):
            modulos = "Todos" if u.admin else ", ".join(TITULOS[Modulo(m)] for m in u.modulos)
            valores = [
                u.nome,
                u.login,
                u.funcao,
                "Sim" if u.admin else "Não",
                modulos,
                "Sim" if u.ativo else "Não",
            ]
            for coluna, valor in enumerate(valores):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(valor))

    def ids_na_tabela(self) -> list[int]:
        return [u.id for u in self._usuarios]

    def usuario_da_linha(self, linha: int) -> Usuario:
        return self._usuarios[linha]

    def _selecionado(self) -> Usuario | None:
        linha = self.tabela.currentRow()
        return None if linha < 0 else self._usuarios[linha]

    def _novo(self) -> None:
        if DialogoUsuario(self._fabrica, self._ator, parent=self).exec():
            self.recarregar()

    def _editar(self) -> None:
        usuario = self._selecionado()
        if usuario and DialogoUsuario(self._fabrica, self._ator, usuario, self).exec():
            self.recarregar()

    def _alterar_senha(self) -> None:
        usuario = self._selecionado()
        if usuario is None:
            return
        nova, ok = QInputDialog.getText(
            self, "Alterar senha", f"Nova senha de {usuario.nome}:", QLineEdit.EchoMode.Password
        )
        if not ok:
            return
        try:
            with transacao(self._fabrica) as s:
                alterar_senha(s, self._ator, usuario.id, nova)
        except ErroDominio as erro:
            mostrar_erro(self, erro)
