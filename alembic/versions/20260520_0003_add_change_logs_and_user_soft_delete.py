"""Add change_logs table and user soft-delete columns.

Revision ID: 20260520_0003
Revises: 20260409_0002
Create Date: 2026-05-20 08:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0003"
down_revision = "20260409_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляет аудит-логи и soft-delete для users."""
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deleted_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_deleted_by_users",
        "users",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
    op.create_index("ix_users_deleted_by", "users", ["deleted_by"])

    op.create_table(
        "change_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_change_logs_entity_type", "change_logs", ["entity_type"])
    op.create_index("ix_change_logs_entity_id", "change_logs", ["entity_id"])
    op.create_index("ix_change_logs_created_by", "change_logs", ["created_by"])


def downgrade() -> None:
    """Откатывает аудит-логи и soft-delete для users."""
    op.drop_index("ix_change_logs_created_by", table_name="change_logs")
    op.drop_index("ix_change_logs_entity_id", table_name="change_logs")
    op.drop_index("ix_change_logs_entity_type", table_name="change_logs")
    op.drop_table("change_logs")

    op.drop_index("ix_users_deleted_by", table_name="users")
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_constraint("fk_users_deleted_by_users", "users", type_="foreignkey")
    op.drop_column("users", "deleted_by")
    op.drop_column("users", "deleted_at")
