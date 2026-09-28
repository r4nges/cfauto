"""clientes: cliente, dependentes e razão de lançamentos

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-28
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "cliente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("nome_busca", sa.String(120), nullable=False),
        sa.Column("celular", sa.String(11), nullable=False),
        sa.Column("cpf", sa.String(11), nullable=True),
        sa.Column("email", sa.String(120), nullable=True),
        sa.Column("endereco", sa.String(200), nullable=False),
        sa.Column("nascimento", sa.Date(), nullable=True),
        sa.Column("sexo", sa.String(20), nullable=True),
        sa.Column("observacoes", sa.String(500), nullable=False),
        sa.Column("limite", sa.Integer(), nullable=True),
        sa.Column("saldo_devedor", sa.Integer(), nullable=False),
        sa.Column("somente_titular", sa.Boolean(), nullable=False),
        sa.Column("aumento_auto", sa.Boolean(), nullable=False),
        sa.Column("aumento_auto_pct", sa.Integer(), nullable=False),
        sa.Column("juros_dias", sa.Integer(), nullable=False),
        sa.Column("juros_frequencia", sa.String(20), nullable=False),
        sa.Column("juros_pct", sa.Integer(), nullable=False),
        sa.Column("juros_mora", sa.Boolean(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_cliente"),
        sa.UniqueConstraint("codigo", name="uq_cliente_codigo"),
    )
    op.create_index("ix_cliente_nome_busca", "cliente", ["nome_busca"])
    op.create_index("ix_cliente_celular", "cliente", ["celular"])
    op.create_index("ix_cliente_cpf", "cliente", ["cpf"])
    op.create_table(
        "cliente_dependente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("parentesco", sa.String(40), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_cliente_dependente"),
        sa.ForeignKeyConstraint(
            ["cliente_id"], ["cliente.id"], name="fk_cliente_dependente_cliente_id_cliente"
        ),
    )
    op.create_index("ix_cliente_dependente_cliente_id", "cliente_dependente", ["cliente_id"])
    op.create_table(
        "cliente_lancamento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("data_hora", sa.DateTime(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("valor", sa.Integer(), nullable=False),
        sa.Column("saldo_apos", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(20), nullable=False),
        sa.Column("observacao", sa.String(200), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_cliente_lancamento"),
        sa.ForeignKeyConstraint(
            ["cliente_id"], ["cliente.id"], name="fk_cliente_lancamento_cliente_id_cliente"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name="fk_cliente_lancamento_usuario_id_usuario"
        ),
    )
    op.create_index(
        "ix_cliente_lancamento_cliente_data", "cliente_lancamento", ["cliente_id", "data_hora"]
    )


def downgrade() -> None:
    op.drop_table("cliente_lancamento")
    op.drop_table("cliente_dependente")
    op.drop_table("cliente")
