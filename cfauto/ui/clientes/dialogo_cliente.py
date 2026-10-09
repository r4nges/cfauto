"""Cadastro de cliente: dados, crédito, dependentes e parâmetros de juros (sem efeito)."""

from collections.abc import Callable
from contextlib import suppress
from decimal import Decimal

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.clientes.cadastro import criar_cliente, editar_cliente, verificar_duplicados
from cfauto.clientes.models import (
    LIMITE_PADRAO,
    MAX_DEPENDENTES,
    TITULOS_FREQUENCIA,
    TITULOS_SEXO,
    FrequenciaJuros,
    Sexo,
)
from cfauto.clientes.schemas import DadosCliente, DadosDependente, FichaCliente, ResumoCliente
from cfauto.clientes.validacao import (
    formatar_celular,
    formatar_cpf,
    formatar_saldo,
    normalizar_celular,
    normalizar_cpf,
)
from cfauto.core.dates import para_data
from cfauto.core.db import transacao
from cfauto.core.errors import ErroDominio, ValorInvalido
from cfauto.core.money import formatar_numero
from cfauto.core.permissoes import Ator
from cfauto.ui.comum import aplicar_mascara_data, ler_decimal, mostrar_erro


def _texto_duplicados(duplicados: list[ResumoCliente]) -> str:
    linhas = "\n".join(f"{c.codigo} — {c.nome} ({formatar_celular(c.celular)})" for c in duplicados)
    return f"Já existe cliente com o mesmo CPF ou celular:\n{linhas}\n\nSalvar mesmo assim?"


class DialogoCliente(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        ficha: FichaCliente | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self.cliente_id: int | None = None if ficha is None else ficha.id
        dados = DadosCliente(nome="", celular="") if ficha is None else ficha.dados
        self.setWindowTitle("Novo cliente" if ficha is None else f"Editar cliente {ficha.codigo}")

        # Dados
        self.nome = QLineEdit(dados.nome)
        self.celular = QLineEdit(formatar_celular(dados.celular))
        self.celular.setPlaceholderText("(11) 98765-4321")
        self.celular.editingFinished.connect(self._formatar_celular)
        self.cpf = QLineEdit(formatar_cpf(dados.cpf))
        self.cpf.setPlaceholderText("000.000.000-00")
        self.cpf.editingFinished.connect(self._formatar_cpf)
        self.email = QLineEdit(dados.email)
        self.nascimento = QLineEdit(
            "" if dados.nascimento is None else f"{dados.nascimento:%d/%m/%Y}"
        )
        self.nascimento.setPlaceholderText("dd/mm/aaaa")
        aplicar_mascara_data(self.nascimento)
        self.sexo = QComboBox()
        self.sexo.addItem("Não informado", None)
        for sexo in Sexo:
            self.sexo.addItem(TITULOS_SEXO[sexo], sexo)
        if dados.sexo is not None:
            self.sexo.setCurrentIndex(list(Sexo).index(dados.sexo) + 1)
        self.endereco = QLineEdit(dados.endereco)
        self.observacoes = QPlainTextEdit(dados.observacoes)
        self.observacoes.setPlaceholderText("Avisos para o caixa")
        self.observacoes.setFixedHeight(60)
        form_dados = QFormLayout()
        form_dados.addRow("Nome", self.nome)
        form_dados.addRow("Celular", self.celular)
        form_dados.addRow("CPF", self.cpf)
        form_dados.addRow("E-mail", self.email)
        form_dados.addRow("Nascimento", self.nascimento)
        form_dados.addRow("Sexo", self.sexo)
        form_dados.addRow("Endereço", self.endereco)
        form_dados.addRow("Observações", self.observacoes)
        grupo_dados = QGroupBox("Dados")
        grupo_dados.setLayout(form_dados)

        # Crédito (limite só admin)
        limite = LIMITE_PADRAO if dados.limite is None else dados.limite
        self.limite = QLineEdit(formatar_numero(limite))
        self.sem_limite = QCheckBox("Sem limite")
        self.sem_limite.setChecked(dados.limite is None)
        self.sem_limite.toggled.connect(self._ao_mudar_sem_limite)
        saldo = Decimal("0.00") if ficha is None else ficha.saldo_devedor
        self.saldo = QLabel(formatar_saldo(saldo))
        form_credito = QFormLayout()
        form_credito.addRow("Limite", self.limite)
        form_credito.addRow("", self.sem_limite)
        form_credito.addRow("Saldo devedor", self.saldo)
        grupo_credito = QGroupBox("Crédito")
        grupo_credito.setLayout(form_credito)
        self.sem_limite.setEnabled(ator.admin)
        self._ao_mudar_sem_limite(self.sem_limite.isChecked())

        # Dependentes
        self.somente_titular = QCheckBox("Somente titular (sem dependentes)")
        self.dependentes_nome = [QLineEdit() for _ in range(MAX_DEPENDENTES)]
        self.dependentes_parentesco = [QLineEdit() for _ in range(MAX_DEPENDENTES)]
        for i, dependente in enumerate(dados.dependentes):
            self.dependentes_nome[i].setText(dependente.nome)
            self.dependentes_parentesco[i].setText(dependente.parentesco)
        grade = QGridLayout()
        grade.addWidget(self.somente_titular, 0, 0, 1, 2)
        grade.addWidget(QLabel("Nome"), 1, 0)
        grade.addWidget(QLabel("Parentesco"), 1, 1)
        for i in range(MAX_DEPENDENTES):
            grade.addWidget(self.dependentes_nome[i], i + 2, 0)
            grade.addWidget(self.dependentes_parentesco[i], i + 2, 1)
        grupo_dependentes = QGroupBox("Dependentes")
        grupo_dependentes.setLayout(grade)
        self.somente_titular.setChecked(dados.somente_titular)
        self.somente_titular.toggled.connect(self._ao_mudar_somente_titular)
        self._ao_mudar_somente_titular(dados.somente_titular)

        # Juros (guardados, sem efeito)
        self.juros_dias = QSpinBox()
        self.juros_dias.setRange(0, 365)
        self.juros_dias.setValue(dados.juros_dias)
        self.juros_frequencia = QComboBox()
        for frequencia in FrequenciaJuros:
            self.juros_frequencia.addItem(TITULOS_FREQUENCIA[frequencia], frequencia)
        self.juros_frequencia.setCurrentIndex(list(FrequenciaJuros).index(dados.juros_frequencia))
        self.juros_pct = QLineEdit(formatar_numero(dados.juros_pct))
        self.juros_mora = QCheckBox("Juros de mora legal")
        self.juros_mora.setChecked(dados.juros_mora)
        self.aumento_auto = QCheckBox("Aumento automático de limite")
        self.aumento_auto.setChecked(dados.aumento_auto)
        self.aumento_auto_pct = QLineEdit(formatar_numero(dados.aumento_auto_pct))
        form_juros = QFormLayout()
        form_juros.addRow("Juros após (dias)", self.juros_dias)
        form_juros.addRow("Frequência", self.juros_frequencia)
        form_juros.addRow("% de juros", self.juros_pct)
        form_juros.addRow("", self.juros_mora)
        form_juros.addRow("", self.aumento_auto)
        form_juros.addRow("% de aumento", self.aumento_auto_pct)
        grupo_juros = QGroupBox("Juros e aumento automático (guardados para uso futuro)")
        grupo_juros.setLayout(form_juros)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.accepted.connect(self._salvar_pelo_botao)
        self.botoes.rejected.connect(self.reject)
        # O formulário é mais alto que muitas telas: rola, e Salvar/Cancelar ficam sempre à vista.
        conteudo = QWidget()
        corpo = QVBoxLayout(conteudo)
        for grupo in (grupo_dados, grupo_credito, grupo_dependentes, grupo_juros):
            corpo.addWidget(grupo)
        self.rolagem = QScrollArea()
        self.rolagem.setWidgetResizable(True)
        self.rolagem.setFrameShape(QFrame.Shape.NoFrame)
        self.rolagem.setWidget(conteudo)
        layout = QVBoxLayout(self)
        layout.addWidget(self.rolagem)
        layout.addWidget(self.botoes)
        self._ajustar_tamanho(conteudo)

    def _ajustar_tamanho(self, conteudo: QWidget) -> None:
        """Abre no tamanho do formulário, limitado a 90% da área útil da tela."""
        util = self.screen().availableGeometry()
        barra = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        ideal = conteudo.sizeHint()
        largura = ideal.width() + barra + 40
        altura = ideal.height() + self.botoes.sizeHint().height() + 40
        self.resize(min(largura, util.width()), min(altura, int(util.height() * 0.9)))

    def _ao_mudar_sem_limite(self, marcado: bool) -> None:
        self.limite.setEnabled(self._ator.admin and not marcado)

    def _ao_mudar_somente_titular(self, marcado: bool) -> None:
        for campo in (*self.dependentes_nome, *self.dependentes_parentesco):
            if marcado:
                campo.clear()
            campo.setEnabled(not marcado)

    def _formatar_celular(self) -> None:
        # Só cosmético: o texto inválido fica como está e o erro aparece ao salvar.
        with suppress(ValorInvalido):
            self.celular.setText(formatar_celular(normalizar_celular(self.celular.text())))

    def _formatar_cpf(self) -> None:
        with suppress(ValorInvalido):
            self.cpf.setText(formatar_cpf(normalizar_cpf(self.cpf.text())))

    def dados(self) -> DadosCliente:
        """Lê o formulário; `ValorInvalido` traz o nome do campo."""
        texto_nascimento = self.nascimento.text().strip()
        try:
            nascimento = para_data(texto_nascimento) if texto_nascimento else None
        except ValorInvalido as erro:
            raise ValorInvalido(f"Nascimento: {erro}") from erro
        sexo = self.sexo.currentData()
        dependentes = tuple(
            DadosDependente(nome=nome.text(), parentesco=parentesco.text())
            for nome, parentesco in zip(
                self.dependentes_nome, self.dependentes_parentesco, strict=True
            )
            if nome.text().strip() or parentesco.text().strip()
        )
        return DadosCliente(
            nome=self.nome.text(),
            celular=self.celular.text(),
            cpf=self.cpf.text(),
            email=self.email.text(),
            endereco=self.endereco.text(),
            nascimento=nascimento,
            sexo=None if sexo is None else Sexo(sexo),
            observacoes=self.observacoes.toPlainText(),
            limite=None
            if self.sem_limite.isChecked()
            else ler_decimal(self.limite.text(), "Limite"),
            somente_titular=self.somente_titular.isChecked(),
            dependentes=dependentes,
            aumento_auto=self.aumento_auto.isChecked(),
            aumento_auto_pct=ler_decimal(self.aumento_auto_pct.text(), "% de aumento"),
            juros_dias=self.juros_dias.value(),
            juros_frequencia=FrequenciaJuros(self.juros_frequencia.currentData()),
            juros_pct=ler_decimal(self.juros_pct.text(), "% de juros"),
            juros_mora=self.juros_mora.isChecked(),
        )

    def _perguntar(self, texto: str) -> bool:
        resposta = QMessageBox.question(self, "CFAUTO", texto)
        return resposta == QMessageBox.StandardButton.Yes

    def _salvar_pelo_botao(self) -> None:
        self.salvar()

    def salvar(self, confirmar: Callable[[str], bool] | None = None) -> None:
        """Valida, avisa de CPF/celular repetido (salvar mesmo assim?) e grava."""
        perguntar = confirmar or self._perguntar
        try:
            dados = self.dados()
            with transacao(self._fabrica) as s:
                duplicados = verificar_duplicados(s, self._ator, dados, self.cliente_id)
            if duplicados and not perguntar(_texto_duplicados(duplicados)):
                return
            with transacao(self._fabrica) as s:
                if self.cliente_id is None:
                    novo_id = criar_cliente(s, self._ator, dados)
                else:
                    editar_cliente(s, self._ator, self.cliente_id, dados)
                    novo_id = self.cliente_id
        except ErroDominio as erro:
            mostrar_erro(self, erro)
            return
        self.cliente_id = novo_id
        self.accept()
