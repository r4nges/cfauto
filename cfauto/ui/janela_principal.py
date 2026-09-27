from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QSizePolicy,
    QStackedWidget,
    QToolBar,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.permissoes import MODULOS_SO_ADMIN, TITULOS, Ator, Modulo, tem_modulo
from cfauto.licenca.service import EstadoLicenca
from cfauto.ui.comum import PaginaEmConstrucao
from cfauto.ui.configuracoes import PaginaConfiguracoes

DIAS_AVISO_LICENCA = 15
LARGURA_NAVEGACAO = 240
FONTE_NAVEGACAO_PT = 12


class JanelaPrincipal(QMainWindow):
    sair = Signal()
    encerrar = Signal()

    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        estado_licenca: EstadoLicenca,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._saindo = False
        self.setWindowTitle("CFAUTO")
        self.resize(1200, 760)

        barra = QToolBar("Sessão")
        barra.setMovable(False)
        self.acao_menu = QAction("☰", self)
        self.acao_menu.setToolTip("Mostrar/ocultar o menu")
        self.acao_menu.triggered.connect(self.alternar_navegacao)
        barra.addAction(self.acao_menu)
        barra.addWidget(QLabel(f"  {ator.nome}  "))
        self.aviso_licenca = QLabel("")
        self.aviso_licenca.setStyleSheet("color: #b9770e; font-weight: bold;")
        dias = estado_licenca.dias_restantes
        if dias is not None and dias <= DIAS_AVISO_LICENCA:
            self.aviso_licenca.setText(f"  Licença expira em {dias} dias  ")
        barra.addWidget(self.aviso_licenca)
        espaco = QWidget()
        espaco.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        barra.addWidget(espaco)
        self.acao_configuracoes = QAction("Configurações", self)
        self.acao_configuracoes.setVisible(ator.admin)
        self.acao_configuracoes.triggered.connect(self.mostrar_configuracoes)
        barra.addAction(self.acao_configuracoes)
        self.acao_sair = QAction("Sair", self)
        self.acao_sair.triggered.connect(self._sair)
        barra.addAction(self.acao_sair)
        self.addToolBar(barra)

        self._navegacao = QListWidget()
        self._navegacao.setFixedWidth(LARGURA_NAVEGACAO)
        self._navegacao.setSpacing(4)
        fonte = self._navegacao.font()
        fonte.setPointSize(FONTE_NAVEGACAO_PT)
        self._navegacao.setFont(fonte)
        self._paginas = QStackedWidget()
        self._navegacao.currentRowChanged.connect(self._ao_trocar_linha)
        self.configuracoes: PaginaConfiguracoes | None = None

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self._navegacao)
        layout.addWidget(self._paginas, 1)
        self.setCentralWidget(central)

        self._montar_paginas()
        self._navegacao.setCurrentRow(0)

    def _montar_paginas(self) -> None:
        # Módulos só-admin ficam fora da navegação, na seção Configurações.
        for modulo in Modulo:
            if modulo not in MODULOS_SO_ADMIN and tem_modulo(self._ator, modulo):
                self.adicionar_pagina(TITULOS[modulo], PaginaEmConstrucao(TITULOS[modulo]))
        if self._ator.admin:
            self.configuracoes = PaginaConfiguracoes(self._fabrica, self._ator)
            self._paginas.addWidget(self.configuracoes)

    def adicionar_pagina(self, titulo: str, widget: QWidget) -> None:
        # Linha i da navegação = página i do stack; Configurações fica depois das páginas.
        self._navegacao.addItem(titulo)
        self._paginas.insertWidget(self._navegacao.count() - 1, widget)

    def titulos_navegacao(self) -> list[str]:
        return [self._navegacao.item(i).text() for i in range(self._navegacao.count())]

    def titulos_configuracoes(self) -> list[str]:
        return [] if self.configuracoes is None else self.configuracoes.titulos()

    def pagina_atual(self) -> QWidget | None:
        return self._paginas.currentWidget()

    def selecionar_modulo(self, linha: int) -> None:
        self._navegacao.setCurrentRow(linha)

    def _ao_trocar_linha(self, linha: int) -> None:
        if linha >= 0:
            self._paginas.setCurrentIndex(linha)

    def mostrar_configuracoes(self) -> None:
        if self.configuracoes is None:
            return
        self._navegacao.setCurrentRow(-1)
        self._navegacao.clearSelection()
        self._paginas.setCurrentWidget(self.configuracoes)

    def navegacao_visivel(self) -> bool:
        return not self._navegacao.isHidden()

    def alternar_navegacao(self) -> None:
        self._navegacao.setVisible(self._navegacao.isHidden())

    def fechar_sessao(self) -> None:
        """Fecha a janela sem emitir `encerrar` (logout ou cancelamento do bloqueio)."""
        self._saindo = True
        self.close()

    def _sair(self) -> None:
        self.fechar_sessao()
        self.sair.emit()

    def closeEvent(self, evento: QCloseEvent) -> None:  # noqa: N802 - API do Qt
        if not self._saindo:
            self.encerrar.emit()
        super().closeEvent(evento)
