"""caixa: sessão, venda, itens, taxas; venda_id no razão e venda_item_id no estoque

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

from cfauto.core import clock

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "sessao_caixa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("protocolo", sa.String(24), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("aberta_em", sa.DateTime(), nullable=False),
        sa.Column("aberta_por", sa.Integer(), nullable=False),
        sa.Column("fundo_troco", sa.Integer(), nullable=False),
        sa.Column("fechada_em", sa.DateTime(), nullable=True),
        sa.Column("fechada_por", sa.Integer(), nullable=True),
        sa.Column("valor_mantido", sa.Integer(), nullable=True),
        sa.Column("sangria", sa.Integer(), nullable=True),
        sa.Column("resumo_json", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_sessao_caixa"),
        sa.UniqueConstraint("protocolo", name="uq_sessao_caixa_protocolo"),
        sa.ForeignKeyConstraint(
            ["aberta_por"], ["usuario.id"], name="fk_sessao_caixa_aberta_por_usuario"
        ),
        sa.ForeignKeyConstraint(
            ["fechada_por"], ["usuario.id"], name="fk_sessao_caixa_fechada_por_usuario"
        ),
    )
    op.create_index(
        "ix_sessao_caixa_aberta",
        "sessao_caixa",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'ABERTA'"),
    )
    op.create_table(
        "venda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sessao_id", sa.Integer(), nullable=False),
        sa.Column("data_hora", sa.DateTime(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("autorizado_por", sa.Integer(), nullable=True),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("forma_pagamento", sa.String(20), nullable=False),
        sa.Column("desconto", sa.Integer(), nullable=False),
        sa.Column("bruto", sa.Integer(), nullable=False),
        sa.Column("taxa", sa.Integer(), nullable=False),
        sa.Column("liquido", sa.Integer(), nullable=False),
        sa.Column("repasse_taxa", sa.Boolean(), nullable=False),
        sa.Column("data_liquidacao", sa.Date(), nullable=True),
        sa.Column("cancelada", sa.Boolean(), nullable=False),
        sa.Column("cancelada_em", sa.DateTime(), nullable=True),
        sa.Column("cancelada_por", sa.Integer(), nullable=True),
        sa.Column("cancelamento_autorizado_por", sa.Integer(), nullable=True),
        sa.Column("motivo_cancelamento", sa.String(200), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_venda"),
        sa.ForeignKeyConstraint(
            ["sessao_id"], ["sessao_caixa.id"], name="fk_venda_sessao_id_sessao_caixa"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], name="fk_venda_usuario_id_usuario"),
        sa.ForeignKeyConstraint(
            ["autorizado_por"], ["usuario.id"], name="fk_venda_autorizado_por_usuario"
        ),
        sa.ForeignKeyConstraint(["cliente_id"], ["cliente.id"], name="fk_venda_cliente_id_cliente"),
        sa.ForeignKeyConstraint(
            ["cancelada_por"], ["usuario.id"], name="fk_venda_cancelada_por_usuario"
        ),
        sa.ForeignKeyConstraint(
            ["cancelamento_autorizado_por"],
            ["usuario.id"],
            name="fk_venda_cancelamento_autorizado_por_usuario",
        ),
    )
    op.create_index("ix_venda_sessao_id", "venda", ["sessao_id"])
    op.create_index("ix_venda_data_hora", "venda", ["data_hora"])
    op.create_index("ix_venda_cliente_id", "venda", ["cliente_id"])
    op.create_table(
        "venda_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venda_id", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=True),
        sa.Column("servico_id", sa.Integer(), nullable=True),
        sa.Column("descricao_snapshot", sa.String(200), nullable=False),
        sa.Column("categoria_snapshot", sa.String(60), nullable=False),
        sa.Column("qtd", sa.Integer(), nullable=False),
        sa.Column("preco_unit", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_venda_item"),
        # op.f: o nome já está completo; sem isso a convenção "ck_%(table_name)s_..." o duplica.
        sa.CheckConstraint(
            "(produto_id IS NULL) <> (servico_id IS NULL)",
            name=op.f("ck_venda_item_produto_xor_servico"),
        ),
        sa.ForeignKeyConstraint(["venda_id"], ["venda.id"], name="fk_venda_item_venda_id_venda"),
        sa.ForeignKeyConstraint(
            ["produto_id"], ["produto.id"], name="fk_venda_item_produto_id_produto"
        ),
        sa.ForeignKeyConstraint(
            ["servico_id"], ["servico.id"], name="fk_venda_item_servico_id_servico"
        ),
    )
    op.create_index("ix_venda_item_venda_id", "venda_item", ["venda_id"])
    op.create_index("ix_venda_item_produto_id", "venda_item", ["produto_id"])
    taxa_pagamento = op.create_table(
        "taxa_pagamento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("forma", sa.String(20), nullable=False),
        sa.Column("pct", sa.Integer(), nullable=False),
        sa.Column("dias", sa.Integer(), nullable=False),
        sa.Column("repasse", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_taxa_pagamento"),
        sa.UniqueConstraint("forma", name="uq_taxa_pagamento_forma"),
    )
    agora = clock.agora()
    # pct é DecimalEscalado(2): inteiro escalado (1,5% = 150).
    op.bulk_insert(
        taxa_pagamento,
        [
            {"forma": forma, "pct": pct, "dias": dias, "repasse": False}
            | {"criado_em": agora, "atualizado_em": agora}
            for forma, pct, dias in (
                ("DINHEIRO", 0, 0),
                ("PIX", 0, 0),
                ("DEBITO", 150, 7),
                ("CREDITO", 350, 7),
            )
        ],
    )
    with op.batch_alter_table("cliente_lancamento") as lote:
        lote.add_column(sa.Column("venda_id", sa.Integer(), nullable=True))
        lote.create_index("ix_cliente_lancamento_venda_id", ["venda_id"])
        lote.create_foreign_key(
            "fk_cliente_lancamento_venda_id_venda", "venda", ["venda_id"], ["id"]
        )
    with op.batch_alter_table("movimento_estoque") as lote:
        lote.add_column(sa.Column("venda_item_id", sa.Integer(), nullable=True))
        lote.create_foreign_key(
            "fk_movimento_estoque_venda_item_id_venda_item",
            "venda_item",
            ["venda_item_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("movimento_estoque") as lote:
        lote.drop_constraint("fk_movimento_estoque_venda_item_id_venda_item", type_="foreignkey")
        lote.drop_column("venda_item_id")
    with op.batch_alter_table("cliente_lancamento") as lote:
        lote.drop_constraint("fk_cliente_lancamento_venda_id_venda", type_="foreignkey")
        lote.drop_index("ix_cliente_lancamento_venda_id")
        lote.drop_column("venda_id")
    op.drop_table("taxa_pagamento")
    op.drop_table("venda_item")
    op.drop_table("venda")
    op.drop_table("sessao_caixa")
