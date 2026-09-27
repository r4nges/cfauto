from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.core.permissoes import TITULOS, Ator, Modulo, tem_modulo
from cfauto.licenca.service import EstadoLicenca
from cfauto.ui.comum import PaginaEmConstrucao

DIAS_AVISO_LICENCA = 15


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
        barra.addWidget(QLabel(f"  {ator.nome}  "))
        self.aviso_licenca = QLabel("")
        self.aviso_licenca.setStyleSheet("color: #b9770e; font-weight: bold;")
        dias = estado_licenca.dias_restantes
        if dias is not None and dias <= DIAS_AVISO_LICENCA:
            self.aviso_licenca.setText(f"  Licença expira em {dias} dias  ")
        barra.addWidget(self.aviso_licenca)
        self.acao_sair = QAction("Sair", self)
        self.acao_sair.triggered.connect(self._sair)
        barra.addAction(self.acao_sair)
        self.addToolBar(barra)

        self._navegacao = QListWidget()
        self._navegacao.setFixedWidth(200)
        self._paginas = QStackedWidget()
        self._navegacao.currentRowChanged.connect(self._paginas.setCurrentIndex)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self._navegacao)
        layout.addWidget(self._paginas, 1)
        self.setCentralWidget(central)

        self._montar_paginas()
        self._navegacao.setCurrentRow(0)

    def _montar_paginas(self) -> None:
        for modulo in Modulo:
            if modulo is Modulo.USUARIOS:
                continue
            if tem_modulo(self._ator, modulo):
                self.adicionar_pagina(TITULOS[modulo], PaginaEmConstrucao(TITULOS[modulo]))
        if self._ator.admin:
            from cfauto.ui.auditoria import TelaAuditoria
            from cfauto.ui.usuarios import TelaUsuarios

            self.adicionar_pagina(TITULOS[Modulo.USUARIOS], TelaUsuarios(self._fabrica, self._ator))
            self.adicionar_pagina("Auditoria", TelaAuditoria(self._fabrica, self._ator))

    def adicionar_pagina(self, titulo: str, widget: QWidget) -> None:
        self._navegacao.addItem(titulo)
        self._paginas.addWidget(widget)

    def titulos_navegacao(self) -> list[str]:
        return [self._navegacao.item(i).text() for i in range(self._navegacao.count())]

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
