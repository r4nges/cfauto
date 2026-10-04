from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

import cfauto.modelos  # noqa: F401
from cfauto.core.db import Base, criar_engine
from cfauto.core.migracoes import PASTA_MIGRACOES, migracoes_pendentes, migrar


def test_migrar_cria_tabelas(engine):
    tabelas = set(inspect(engine).get_table_names())
    assert {"usuario", "audit_log", "config_item", "licenca_estado"} <= tabelas


def test_sem_pendencias_apos_migrar(engine):
    assert migracoes_pendentes(engine) is False


def test_banco_novo_tem_pendencias(tmp_path):
    engine = criar_engine(f"sqlite:///{tmp_path / 'novo.db'}")
    assert migracoes_pendentes(engine) is True
    migrar(engine)
    assert migracoes_pendentes(engine) is False
    engine.dispose()


def test_modelos_batem_com_migracoes(engine):
    with engine.connect() as conexao:
        contexto = MigrationContext.configure(conexao, opts={"compare_type": True})
        diferencas = compare_metadata(contexto, Base.metadata)
    assert diferencas == []


def _subir_ate(engine, revisao):
    cfg = Config()
    cfg.set_main_option("script_location", str(PASTA_MIGRACOES))
    with engine.begin() as conexao:
        cfg.attributes["connection"] = conexao
        command.upgrade(cfg, revisao)


def test_0004_preserva_razao_e_movimentos_existentes_na_0003(tmp_path):
    """O `batch_alter_table` recria as tabelas no SQLite: as linhas da 0003 têm de sobreviver."""
    engine = criar_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    _subir_ate(engine, "0003")
    agora = "2026-09-23 10:00:00"
    with engine.begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO usuario (id, nome, funcao, login, admin, modulos, tentativas_falhas,"
                " ativo, criado_em, atualizado_em) VALUES (1, 'Dono', '', 'dono', 1, '[]', 0, 1,"
                " :agora, :agora)"
            ),
            {"agora": agora},
        )
        conexao.execute(
            text(
                "INSERT INTO cliente (id, codigo, nome, nome_busca, celular, endereco,"
                " observacoes, saldo_devedor, somente_titular, aumento_auto, aumento_auto_pct,"
                " juros_dias, juros_frequencia, juros_pct, juros_mora, ativo, criado_em,"
                " atualizado_em) VALUES (1, 'CLI-0001', 'Ana Souza', 'ana souza', '11987654321',"
                " '', '', 3000, 0, 0, 0, 0, 'MENSAL', 0, 0, 1, :agora, :agora)"
            ),
            {"agora": agora},
        )
        conexao.execute(
            text(
                "INSERT INTO produto (id, codigo, descricao, categoria, embalagem, fator,"
                " preco_entrada, preco_venda, estoque, estoque_minimo, estoque_minimo_manual,"
                " destino, markup_manual, ativo, criado_em, atualizado_em) VALUES (1, '0001',"
                " 'Óleo 5W30', 'Lubrificantes', 'Unidade', 1000, 0, 3000, 10000, 0, 0, 'REVENDA',"
                " 0, 1, :agora, :agora)"
            ),
            {"agora": agora},
        )
        conexao.execute(
            text(
                "INSERT INTO cliente_lancamento (id, cliente_id, data_hora, tipo, valor,"
                " saldo_apos, motivo, observacao, usuario_id, criado_em, atualizado_em)"
                " VALUES (1, 1, :agora, 'DEBITO', 3000, 3000, 'COMPRA_ANOTADA', 'antigo', 1,"
                " :agora, :agora)"
            ),
            {"agora": agora},
        )
        conexao.execute(
            text(
                "INSERT INTO movimento_estoque (id, produto_id, data_hora, tipo, quantidade,"
                " saldo_apos, usuario_id, observacao, criado_em, atualizado_em) VALUES (1, 1,"
                " :agora, 'AJUSTE', 10000, 10000, 1, 'antigo', :agora, :agora)"
            ),
            {"agora": agora},
        )

    _subir_ate(engine, "0004")

    with engine.connect() as conexao:
        lancamento = conexao.execute(
            text(
                "SELECT cliente_id, tipo, valor, saldo_apos, observacao, venda_id"
                " FROM cliente_lancamento"
            )
        ).one()
        movimento = conexao.execute(
            text(
                "SELECT produto_id, tipo, quantidade, saldo_apos, observacao, venda_item_id"
                " FROM movimento_estoque"
            )
        ).one()
        taxas = conexao.execute(text("SELECT count(*) FROM taxa_pagamento")).scalar_one()
    assert tuple(lancamento) == (1, "DEBITO", 3000, 3000, "antigo", None)
    assert tuple(movimento) == (1, "AJUSTE", 10000, 10000, "antigo", None)
    assert taxas == 4
    engine.dispose()
