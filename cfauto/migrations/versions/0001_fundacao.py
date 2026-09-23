"""fundação: usuário, auditoria, config, licença

Revision ID: 0001
Revises:
Create Date: 2026-09-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("funcao", sa.String(60), nullable=False),
        sa.Column("login", sa.String(60), nullable=False),
        sa.Column("senha_hash", sa.String(255), nullable=True),
        sa.Column("hash_legado", sa.String(64), nullable=True),
        sa.Column("admin", sa.Boolean(), nullable=False),
        sa.Column("modulos", sa.JSON(), nullable=False),
        sa.Column("tentativas_falhas", sa.Integer(), nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_usuario"),
        sa.UniqueConstraint("login", name="uq_usuario_login"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("acao", sa.String(40), nullable=False),
        sa.Column("entidade", sa.String(60), nullable=False),
        sa.Column("entidade_id", sa.String(60), nullable=True),
        sa.Column("antes", sa.JSON(), nullable=True),
        sa.Column("depois", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name="fk_audit_log_usuario_id_usuario"
        ),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_entidade", "audit_log", ["entidade"])
    op.create_table(
        "config_item",
        sa.Column("chave", sa.String(100), nullable=False),
        sa.Column("valor", sa.JSON(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("chave", name="pk_config_item"),
    )
    op.create_table(
        "licenca_estado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chave", sa.Text(), nullable=True),
        sa.Column("ultima_data_vista", sa.Date(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_licenca_estado"),
    )


def downgrade() -> None:
    op.drop_table("licenca_estado")
    op.drop_table("config_item")
    op.drop_index("ix_audit_log_entidade", table_name="audit_log")
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("usuario")
