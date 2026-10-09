import pytest
from PySide6.QtGui import QFont, QPalette


@pytest.fixture
def tema_isolado(qapp):
    """Entrega a QApplication e desfaz no fim o que `aplicar_tema` mudou nela."""
    estilo = qapp.style().objectName()
    paleta = QPalette(qapp.palette())
    fonte = QFont(qapp.font())
    folha = qapp.styleSheet()
    yield qapp
    qapp.setStyleSheet(folha)
    qapp.setStyle(estilo)
    qapp.setPalette(paleta)
    qapp.setFont(fonte)
    qapp.styleHints().unsetColorScheme()
