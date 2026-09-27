"""Ponto de entrada: provisiona, garante licença, faz login e abre a janela principal."""

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from cfauto.core import config
from cfauto.core.db import transacao
from cfauto.core.logs import configurar_logs
from cfauto.core.permissoes import Ator
from cfauto.jobs.agendador import Agendador
from cfauto.jobs.catalogo import jobs_padrao
from cfauto.jobs.runner import catchup
from cfauto.licenca.service import EstadoLicenca, avaliar
from cfauto.sistema.provisionamento import Ambiente, caminhos_padrao, fazer_backup, inicializar
from cfauto.ui.assistente import AssistentePrimeiraExecucao
from cfauto.ui.inatividade import MonitorInatividade
from cfauto.ui.janela_principal import JanelaPrincipal
from cfauto.ui.licenca import DialogoLicenca
from cfauto.ui.login import DialogoLogin

log = logging.getLogger("cfauto.ui")
MINUTOS_INATIVIDADE_PADRAO = 15


class Aplicacao:
    def __init__(self, qapp: QApplication, ambiente: Ambiente) -> None:
        self._qapp = qapp
        self._ambiente = ambiente
        self._fabrica = ambiente.fabrica
        self._jobs = jobs_padrao(ambiente)
        self._agendador = Agendador(self._fabrica, self._jobs)
        self._janela: JanelaPrincipal | None = None
        self._ator: Ator | None = None
        self._estado_licenca: EstadoLicenca | None = None
        with transacao(self._fabrica) as s:
            minutos = int(
                config.obter(s, "seguranca.minutos_inatividade", MINUTOS_INATIVIDADE_PADRAO)
            )
        self._monitor = MonitorInatividade(minutos * 60_000)
        self._monitor.inativo.connect(self._bloquear)
        qapp.aboutToQuit.connect(self._ao_sair)

    def executar(self) -> int:
        if self._ambiente.primeira_execucao:
            assistente = AssistentePrimeiraExecucao(self._fabrica)
            if not assistente.exec():  # exec() devolve int: 1 = aceito
                return 0
        if not self._garantir_licenca():
            return 0
        falhas = {n: e for n, e in catchup(self._fabrica, self._jobs).items() if e is not None}
        if falhas:
            QMessageBox.warning(
                None, "CFAUTO", "Tarefas automáticas com falha: " + ", ".join(sorted(falhas))
            )
        self._agendador.iniciar()
        if not self._login():
            return 0
        return self._qapp.exec()

    def _garantir_licenca(self) -> bool:
        while True:
            with transacao(self._fabrica) as s:
                estado = avaliar(s)
            if estado.valida:
                self._estado_licenca = estado
                return True
            dialogo = DialogoLicenca(self._fabrica, estado)
            if not dialogo.exec():
                return False

    def _login(self) -> bool:
        dialogo = DialogoLogin(self._fabrica)
        if not dialogo.exec() or dialogo.ator is None:
            return False
        self._abrir_janela(dialogo.ator)
        return True

    def _abrir_janela(self, ator: Ator) -> None:
        assert self._estado_licenca is not None
        self._ator = ator
        self._janela = JanelaPrincipal(self._fabrica, ator, self._estado_licenca)
        self._janela.sair.connect(self._logout)
        self._janela.encerrar.connect(self._qapp.quit)
        self._janela.show()
        self._monitor.reiniciar()

    def _logout(self) -> None:
        self._monitor.parar()
        if self._janela is not None:
            self._janela.fechar_sessao()
            self._janela.deleteLater()
            self._janela = None
        if not self._login():
            self._qapp.quit()

    def _bloquear(self) -> None:
        if self._janela is None or self._ator is None:
            return
        self._janela.hide()
        dialogo = DialogoLogin(self._fabrica, login_fixo=self._ator.login)
        if dialogo.exec():
            self._janela.show()
            self._monitor.reiniciar()
        else:
            self._logout()

    def _ao_sair(self) -> None:
        self._agendador.parar()
        try:
            fazer_backup(self._ambiente.caminhos.db, self._ambiente.caminhos.backups)
        except Exception:
            log.exception("backup ao sair falhou")


def main(argv: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    caminhos = caminhos_padrao()
    configurar_logs(caminhos.logs)
    if "--verificar-instalacao" in argumentos:
        ambiente = inicializar(caminhos)
        ambiente.engine.dispose()
        return 0
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("CFAUTO")
    qapp.setQuitOnLastWindowClosed(False)
    try:
        ambiente = inicializar(caminhos)
    except Exception:
        log.exception("falha ao inicializar o banco")
        QMessageBox.critical(
            None, "CFAUTO", f"Falha ao iniciar o banco de dados. Veja o log em {caminhos.logs}."
        )
        return 1
    return Aplicacao(qapp, ambiente).executar()
