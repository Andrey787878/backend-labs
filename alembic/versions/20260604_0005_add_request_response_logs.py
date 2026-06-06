"""Add request/response logs for LR7.

Revision ID: 20260604_0005
Revises: 20260520_0004
Create Date: 2026-06-04 14:50:00
"""

from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "20260604_0005"
down_revision = "20260520_0004"
branch_labels = None
depends_on = None


LOG_PERMISSIONS: tuple[tuple[str, str, str | None], ...] = (
    ("get-list-log", "get-list-log", "Просмотр списка request/response логов"),
    ("read-log", "read-log", "Просмотр полной записи request/response лога"),
    ("delete-log", "delete-log", "Удаление request/response лога"),
)


def _resolve_seed_user_id(connection: sa.Connection) -> int:
    """Возвращает id пользователя для заполнения created_by в permission seed."""
    existing_user_id = connection.execute(sa.text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
    if existing_user_id is not None:
        return int(existing_user_id)

    raise RuntimeError("Невозможно добавить log-permissions: таблица users пуста.")


def upgrade() -> None:
    """Создает logs_requests и назначает log-permissions роли admin."""
    op.create_table(
        "logs_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("full_url", sa.String(length=2048), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("controller_path", sa.String(length=512), nullable=True),
        sa.Column("controller_method", sa.String(length=128), nullable=True),
        sa.Column("request_body", sa.JSON(), nullable=True),
        sa.Column("request_headers", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("response_status", sa.SmallInteger(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("response_headers", sa.JSON(), nullable=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_logs_requests_user_id", "logs_requests", ["user_id"])
    op.create_index("ix_logs_requests_response_status", "logs_requests", ["response_status"])
    op.create_index("ix_logs_requests_ip_address", "logs_requests", ["ip_address"])
    op.create_index("ix_logs_requests_controller_path", "logs_requests", ["controller_path"])
    op.create_index("ix_logs_requests_called_at", "logs_requests", ["called_at"])

    connection = op.get_bind()
    seed_user_id = _resolve_seed_user_id(connection)

    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("created_by", sa.Integer()),
    )

    existing_slugs = {
        str(row[0])
        for row in connection.execute(
            sa.text("SELECT slug FROM permissions WHERE slug = ANY(:slugs)"),
            {"slugs": [item[1] for item in LOG_PERMISSIONS]},
        ).all()
    }

    insert_rows: list[dict[str, Any]] = []
    for name, slug, description in LOG_PERMISSIONS:
        if slug in existing_slugs:
            continue
        insert_rows.append(
            {
                "name": name,
                "slug": slug,
                "description": description,
                "created_by": seed_user_id,
            }
        )

    if insert_rows:
        connection.execute(sa.insert(permission_table), insert_rows)

    admin_role_id = connection.execute(
        sa.text("SELECT id FROM roles WHERE slug = :slug LIMIT 1"),
        {"slug": "admin"},
    ).scalar()
    if admin_role_id is None:
        raise RuntimeError("Невозможно назначить log-permissions: роль admin не найдена.")

    permission_rows = connection.execute(
        sa.text("SELECT id, slug FROM permissions WHERE slug = ANY(:slugs)"),
        {"slugs": [item[1] for item in LOG_PERMISSIONS]},
    ).mappings()

    permission_role_table = sa.table(
        "permission_role",
        sa.column("role_id", sa.Integer()),
        sa.column("permission_id", sa.Integer()),
        sa.column("created_by", sa.Integer()),
    )

    for row in permission_rows:
        permission_id = int(row["id"])
        exists = connection.execute(
            sa.text(
                """
                SELECT 1
                FROM permission_role
                WHERE role_id = :role_id
                  AND permission_id = :permission_id
                LIMIT 1
                """
            ),
            {"role_id": int(admin_role_id), "permission_id": permission_id},
        ).scalar()

        if exists:
            continue

        connection.execute(
            sa.insert(permission_role_table),
            {
                "role_id": int(admin_role_id),
                "permission_id": permission_id,
                "created_by": seed_user_id,
            },
        )


def downgrade() -> None:
    """Удаляет logs_requests и log-permissions."""
    connection = op.get_bind()
    slugs = [item[1] for item in LOG_PERMISSIONS]

    permission_ids = [
        int(row[0])
        for row in connection.execute(
            sa.text("SELECT id FROM permissions WHERE slug = ANY(:slugs)"),
            {"slugs": slugs},
        ).all()
    ]

    if permission_ids:
        connection.execute(
            sa.text("DELETE FROM permission_role WHERE permission_id = ANY(:permission_ids)"),
            {"permission_ids": permission_ids},
        )

    connection.execute(sa.text("DELETE FROM permissions WHERE slug = ANY(:slugs)"), {"slugs": slugs})

    op.drop_index("ix_logs_requests_called_at", table_name="logs_requests")
    op.drop_index("ix_logs_requests_controller_path", table_name="logs_requests")
    op.drop_index("ix_logs_requests_ip_address", table_name="logs_requests")
    op.drop_index("ix_logs_requests_response_status", table_name="logs_requests")
    op.drop_index("ix_logs_requests_user_id", table_name="logs_requests")
    op.drop_table("logs_requests")
