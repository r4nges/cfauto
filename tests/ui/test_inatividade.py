from cfauto.ui.inatividade import MonitorInatividade


def test_emite_inativo(qtbot):
    monitor = MonitorInatividade(50)
    with qtbot.waitSignal(monitor.inativo, timeout=1000):
        monitor.reiniciar()
    monitor.parar()
