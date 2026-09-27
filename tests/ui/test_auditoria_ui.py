from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core.audit import registrar
from cfauto.core.db import transacao
from cfauto.ui.auditoria import TelaAuditoria


def test_tela_auditoria_filtra(qtbot, fabrica, relogio):
    with transacao(fabrica) as s:
        admin = criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )
        registrar(s, admin.id, "alterar", "produto", 1, {"preco": "1"}, {"preco": "2"})
    tela = TelaAuditoria(fabrica, admin)
    qtbot.addWidget(tela)
    assert tela.tabela.rowCount() == 2
    tela.filtro_entidade.setText("produto")
    tela.filtrar()
    assert tela.tabela.rowCount() == 1
    assert tela.tabela.item(0, 1).text() == "Dono"
    assert tela.tabela.item(0, 3).text() == "produto"
