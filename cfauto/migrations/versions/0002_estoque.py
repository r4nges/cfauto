"""estoque: sequência, produto, serviço, movimentos, notas de entrada, bens físicos

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "sequencia",
        sa.Column("nome", sa.String(40), nullable=False),
        sa.Column("ultimo", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("nome", name="pk_sequencia"),
    )
    op.create_table(
        "produto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("ean", sa.String(14), nullable=True),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("categoria", sa.String(60), nullable=False),
        sa.Column("embalagem", sa.String(30), nullable=False),
        sa.Column("fator", sa.Integer(), nullable=False),
        sa.Column("data_ult_entrada", sa.Date(), nullable=True),
        sa.Column("preco_entrada", sa.Integer(), nullable=False),
        sa.Column("preco_venda", sa.Integer(), nullable=False),
        sa.Column("preco_promocional", sa.Integer(), nullable=True),
        sa.Column("estoque", sa.Integer(), nullable=False),
        sa.Column("estoque_minimo", sa.Integer(), nullable=False),
        sa.Column("estoque_minimo_manual", sa.Boolean(), nullable=False),
        sa.Column("destino", sa.String(20), nullable=False),
        sa.Column("markup_pct", sa.Integer(), nullable=True),
        sa.Column("markup_manual", sa.Boolean(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_produto"),
        sa.UniqueConstraint("codigo", name="uq_produto_codigo"),
        sa.UniqueConstraint("ean", name="uq_produto_ean"),
    )
    op.create_table(
        "servico",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("mao_obra_pct", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_servico"),
        sa.UniqueConstraint("codigo", name="uq_servico_codigo"),
    )
    op.create_table(
        "servico_material",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("servico_id", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.String(120), nullable=False),
        sa.Column("custo_unit", sa.Integer(), nullable=False),
        sa.Column("qtd", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_servico_material"),
        sa.ForeignKeyConstraint(
            ["servico_id"], ["servico.id"], name="fk_servico_material_servico_id_servico"
        ),
    )
    op.create_index("ix_servico_material_servico_id", "servico_material", ["servico_id"])
    op.create_table(
        "nota_entrada",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chave", sa.String(44), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("serie", sa.Integer(), nullable=False),
        sa.Column("modelo", sa.Integer(), nullable=False),
        sa.Column("emitente_cnpj", sa.String(14), nullable=False),
        sa.Column("emitente_nome", sa.String(120), nullable=False),
        sa.Column("data_emissao", sa.Date(), nullable=False),
        sa.Column("data_entrada", sa.DateTime(), nullable=False),
        sa.Column("valor_total", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("xml_original", sa.LargeBinary(), nullable=False),
        sa.Column("estornada", sa.Boolean(), nullable=False),
        sa.Column("estornada_em", sa.DateTime(), nullable=True),
        sa.Column("estornada_por", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_nota_entrada"),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name="fk_nota_entrada_usuario_id_usuario"
        ),
        sa.ForeignKeyConstraint(
            ["estornada_por"], ["usuario.id"], name="fk_nota_entrada_estornada_por_usuario"
        ),
    )
    op.create_index(
        "ix_nota_entrada_chave_ativa",
        "nota_entrada",
        ["chave"],
        unique=True,
        sqlite_where=sa.text("estornada = 0"),
    )
    op.create_table(
        "nota_entrada_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nota_id", sa.Integer(), nullable=False),
        sa.Column("n_item", sa.Integer(), nullable=False),
        sa.Column("codigo_fornecedor", sa.String(60), nullable=False),
        sa.Column("ean", sa.String(14), nullable=True),
        sa.Column("descricao_nota", sa.String(200), nullable=False),
        sa.Column("unidade", sa.String(10), nullable=False),
        sa.Column("qtd_nota", sa.Integer(), nullable=False),
        sa.Column("valor_produto", sa.Integer(), nullable=False),
        sa.Column("desconto", sa.Integer(), nullable=False),
        sa.Column("frete", sa.Integer(), nullable=False),
        sa.Column("seguro", sa.Integer(), nullable=False),
        sa.Column("outros", sa.Integer(), nullable=False),
        sa.Column("ipi", sa.Integer(), nullable=False),
        sa.Column("icms_st", sa.Integer(), nullable=False),
        sa.Column("custo_total", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=True),
        sa.Column("fator", sa.Integer(), nullable=True),
        sa.Column("qtd_estoque", sa.Integer(), nullable=True),
        sa.Column("preco_entrada_aplicado", sa.Integer(), nullable=True),
        sa.Column("preco_entrada_anterior", sa.Integer(), nullable=True),
        sa.Column("data_ult_entrada_anterior", sa.Date(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_nota_entrada_item"),
        sa.ForeignKeyConstraint(
            ["nota_id"], ["nota_entrada.id"], name="fk_nota_entrada_item_nota_id_nota_entrada"
        ),
        sa.ForeignKeyConstraint(
            ["produto_id"], ["produto.id"], name="fk_nota_entrada_item_produto_id_produto"
        ),
    )
    op.create_index("ix_nota_entrada_item_nota_id", "nota_entrada_item", ["nota_id"])
    op.create_index("ix_nota_entrada_item_produto_id", "nota_entrada_item", ["produto_id"])
    op.create_table(
        "movimento_estoque",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("data_hora", sa.DateTime(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("saldo_apos", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(20), nullable=True),
        sa.Column("observacao", sa.String(200), nullable=True),
        sa.Column("nota_entrada_item_id", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_movimento_estoque"),
        sa.ForeignKeyConstraint(
            ["produto_id"], ["produto.id"], name="fk_movimento_estoque_produto_id_produto"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name="fk_movimento_estoque_usuario_id_usuario"
        ),
        sa.ForeignKeyConstraint(
            ["nota_entrada_item_id"],
            ["nota_entrada_item.id"],
            name="fk_movimento_estoque_nota_entrada_item_id_nota_entrada_item",
        ),
    )
    op.create_index("ix_movimento_estoque_produto_id", "movimento_estoque", ["produto_id"])
    op.create_index("ix_movimento_estoque_data_hora", "movimento_estoque", ["data_hora"])
    op.create_table(
        "vinculo_fornecedor_produto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("emitente_cnpj", sa.String(14), nullable=False),
        sa.Column("codigo_fornecedor", sa.String(60), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("fator", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_vinculo_fornecedor_produto"),
        sa.ForeignKeyConstraint(
            ["produto_id"], ["produto.id"], name="fk_vinculo_fornecedor_produto_produto_id_produto"
        ),
        sa.UniqueConstraint(
            "emitente_cnpj",
            "codigo_fornecedor",
            name="uq_vinculo_fornecedor_produto_emitente_cnpj",
        ),
    )
    op.create_table(
        "bem_fisico",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("valor", sa.Integer(), nullable=False),
        sa.Column("data_cadastro", sa.Date(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_bem_fisico"),
        sa.UniqueConstraint("codigo", name="uq_bem_fisico_codigo"),
    )


def downgrade() -> None:
    op.drop_table("bem_fisico")
    op.drop_table("vinculo_fornecedor_produto")
    op.drop_table("movimento_estoque")
    op.drop_table("nota_entrada_item")
    op.drop_table("nota_entrada")
    op.drop_table("servico_material")
    op.drop_table("servico")
    op.drop_table("produto")
    op.drop_table("sequencia")
