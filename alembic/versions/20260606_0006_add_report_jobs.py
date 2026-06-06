"""Add queued analytics report jobs for LR8.

Revision ID: 20260606_0006
Revises: 20260604_0005
Create Date: 2026-06-06 08:00:00
"""

from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "20260606_0006"
down_revision = "20260604_0005"
branch_labels = None
depends_on = None


REPORT_PERMISSIONS: tuple[tuple[str, str, str | None], ...] = (
    ("generate-report", "generate-report", "Постановка аналитического отчёта в очередь"),
)


def _resolve_seed_user_id(connection: sa.Connection) -> int:
    """Возвращает id пользователя для заполнения created_by в permission seed."""
    existing_user_id = connection.execute(sa.text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
    if existing_user_id is not None:
        return int(existing_user_id)

    raise RuntimeError("Невозможно добавить report-permissions: таблица users пуста.")


def upgrade() -> None:
    """Создает report_jobs и назначает generate-report роли admin."""
    op.create_table(
        "report_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("report_path", sa.String(length=1024), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_report_jobs_status", "report_jobs", ["status"])
    op.create_index("ix_report_jobs_run_after", "report_jobs", ["run_after"])
    op.create_index("ix_report_jobs_created_by", "report_jobs", ["created_by"])
    op.create_index("ix_report_jobs_created_at", "report_jobs", ["created_at"])

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
            {"slugs": [item[1] for item in REPORT_PERMISSIONS]},
        ).all()
    }

    insert_rows: list[dict[str, Any]] = []
    for name, slug, description in REPORT_PERMISSIONS:
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
        raise RuntimeError("Невозможно назначить generate-report: роль admin не найдена.")

    permission_rows = connection.execute(
        sa.text("SELECT id, slug FROM permissions WHERE slug = ANY(:slugs)"),
        {"slugs": [item[1] for item in REPORT_PERMISSIONS]},
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
    """Удаляет report_jobs и permission generate-report."""
    connection = op.get_bind()
    slugs = [item[1] for item in REPORT_PERMISSIONS]

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

    op.drop_index("ix_report_jobs_created_at", table_name="report_jobs")
    op.drop_index("ix_report_jobs_created_by", table_name="report_jobs")
    op.drop_index("ix_report_jobs_run_after", table_name="report_jobs")
    op.drop_index("ix_report_jobs_status", table_name="report_jobs")
    op.drop_table("report_jobs")
