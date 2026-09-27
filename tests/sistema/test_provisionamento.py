from sqlalchemy import inspect

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core.db import transacao
from cfauto.sistema.provisionamento import Caminhos, caminhos_padrao, fazer_backup, inicializar


def test_caminhos_padrao_respeita_cfauto_home(monkeypatch, tmp_path):
    monkeypatch.setenv("CFAUTO_HOME", str(tmp_path))
    c = caminhos_padrao()
    assert c.db == tmp_path / "cfauto.db"
    assert c.backups == tmp_path / "backups"
    assert c.logs == tmp_path / "logs"


def test_caminhos_padrao_usa_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv("CFAUTO_HOME", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert caminhos_padrao().base == tmp_path / "CFAUTO"


def test_backup_mantem_os_sete_mais_recentes(tmp_path, relogio):
    c = Caminhos(tmp_path)
    ambiente = inicializar(c)
    ambiente.engine.dispose()
    gerados = []
    for _ in range(9):
        gerados.append(fazer_backup(c.db, c.backups))
        relogio.avancar(seconds=1)
    restantes = sorted(c.backups.glob("cfauto-*.db"))
    assert len(restantes) == 7
    assert restantes == sorted(gerados[-7:])


def test_backup_sem_banco(tmp_path):
    assert fazer_backup(tmp_path / "nao.db", tmp_path / "b") is None


def test_inicializar_pasta_vazia(tmp_path, relogio):
    ambiente = inicializar(Caminhos(tmp_path / "dados"))
    assert ambiente.primeira_execucao is True
    assert ambiente.caminhos.db.exists()
    assert "usuario" in inspect(ambiente.engine).get_table_names()
    assert not ambiente.caminhos.backups.exists()
    ambiente.engine.dispose()


def test_inicializar_com_usuario(tmp_path, relogio):
    c = Caminhos(tmp_path)
    ambiente = inicializar(c)
    with transacao(ambiente.fabrica) as s:
        criar_usuario(s, None, NovoUsuario(nome="Dono", login="dono", senha="123456", admin=True))
    ambiente.engine.dispose()
    de_novo = inicializar(c)
    assert de_novo.primeira_execucao is False
    assert not c.backups.exists()  # nada pendente, nenhum backup de migração
    de_novo.engine.dispose()
