import logging
from datetime import datetime, timedelta

import pytest

from cfauto.jobs.agendador import Agendador
from cfauto.jobs.catalogo import jobs_padrao
from cfauto.jobs.modelo import Job, a_cada, diario
from cfauto.jobs.runner import catchup, rodar, ultima_execucao
from cfauto.sistema.provisionamento import Caminhos, inicializar

AGORA = datetime(2026, 9, 23, 10, 0)


def test_diario():
    assert diario(None, AGORA)
    assert diario(datetime(2026, 9, 22, 23, 59), AGORA)
    assert not diario(datetime(2026, 9, 23, 0, 5), AGORA)


def test_a_cada():
    semanal = a_cada(timedelta(days=7))
    assert semanal(None, AGORA)
    assert semanal(AGORA - timedelta(days=7), AGORA)
    assert not semanal(AGORA - timedelta(days=6), AGORA)


def _job(nome, chamadas, falhar=False, precisa=diario):
    def executar():
        chamadas.append(nome)
        if falhar:
            raise RuntimeError("boom")

    return Job(nome=nome, executar=executar, cron={"hour": 0, "minute": 5}, precisa_catchup=precisa)


def test_rodar_grava_ultima_execucao(fabrica, relogio):
    chamadas = []
    assert ultima_execucao(fabrica, "a") is None
    rodar(fabrica, _job("a", chamadas))
    assert chamadas == ["a"]
    assert ultima_execucao(fabrica, "a") == AGORA


def test_rodar_falha_propaga_e_nao_grava(fabrica, relogio):
    with pytest.raises(RuntimeError):
        rodar(fabrica, _job("a", [], falhar=True))
    assert ultima_execucao(fabrica, "a") is None


def test_rodar_falha_bookkeeping_loga_e_propaga(fabrica, relogio, monkeypatch, caplog):
    def _falha(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("cfauto.jobs.runner.config.definir", _falha)
    with caplog.at_level(logging.ERROR, logger="cfauto.jobs"), pytest.raises(RuntimeError):
        rodar(fabrica, _job("a", []))
    assert "job a falhou" in caplog.text


def test_catchup_roda_so_pendentes_e_isola_erros(fabrica, relogio):
    chamadas = []
    rodar(fabrica, _job("ja_rodou", chamadas))
    chamadas.clear()
    resultado = catchup(
        fabrica,
        [_job("ja_rodou", chamadas), _job("quebra", chamadas, falhar=True), _job("ok", chamadas)],
    )
    assert chamadas == ["quebra", "ok"]
    assert set(resultado) == {"quebra", "ok"}
    assert isinstance(resultado["quebra"], RuntimeError)
    assert resultado["ok"] is None


def test_agendador_registra_e_para(fabrica):
    agendador = Agendador(fabrica, [_job("a", []), _job("b", [])])
    agendador.iniciar()
    try:
        assert sorted(agendador.nomes_agendados()) == ["a", "b"]
    finally:
        agendador.parar()


def test_catalogo_backup(tmp_path, relogio):
    ambiente = inicializar(Caminhos(tmp_path))
    jobs = {j.nome: j for j in jobs_padrao(ambiente)}
    assert set(jobs) == {"backup"}
    jobs["backup"].executar()
    assert len(list((tmp_path / "backups").glob("cfauto-*.db"))) == 1
    ambiente.engine.dispose()
