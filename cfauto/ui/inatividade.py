from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

_EVENTOS = {
    QEvent.Type.MouseMove,
    QEvent.Type.MouseButtonPress,
    QEvent.Type.KeyPress,
    QEvent.Type.Wheel,
}


class MonitorInatividade(QObject):
    inativo = Signal()

    def __init__(self, intervalo_ms: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.inativo)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def eventFilter(self, obj: QObject, evento: QEvent) -> bool:  # noqa: N802 - API do Qt
        if evento.type() in _EVENTOS and self._timer.isActive():
            self._timer.start()
        return False

    def reiniciar(self) -> None:
        self._timer.start()

    def parar(self) -> None:
        self._timer.stop()
