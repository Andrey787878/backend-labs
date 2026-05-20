"""Seed story permissions for audit endpoints.

Revision ID: 20260520_0004
Revises: 20260520_0003
Create Date: 2026-05-20 08:35:00
"""

from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "20260520_0004"
down_revision = "20260520_0003"
branch_labels = None
depends_on = None


STORY_PERMISSIONS: tuple[tuple[str, str, str | None], ...] = (
    ("get-story-user", "get-story-user", "Просмотр истории изменений пользователей"),
    ("get-story-role", "get-story-role", "Просмотр истории изменений ролей"),
    (
        "get-story-permission",
        "get-story-permission",
        "Просмотр истории изменений разрешений",
    ),
)


def _resolve_seed_user_id(connection: sa.Connection) -> int:
    """Возвращает id пользователя для заполнения created_by в сид-миграции."""
    existing_user_id = connection.execute(sa.text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
    if existing_user_id is not None:
        return int(existing_user_id)

    raise RuntimeError("Невозможно добавить story-permissions: таблица users пуста.")


def upgrade() -> None:
    """Добавляет get-story permissions и назначает их роли admin."""
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
            sa.text(
                "SELECT slug FROM permissions WHERE slug = ANY(:slugs)"
            ),
            {"slugs": [item[1] for item in STORY_PERMISSIONS]},
        ).all()
    }

    insert_rows: list[dict[str, Any]] = []
    for name, slug, description in STORY_PERMISSIONS:
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
        raise RuntimeError("Невозможно назначить story-permissions: роль admin не найдена.")

    permission_rows = connection.execute(
        sa.text("SELECT id, slug FROM permissions WHERE slug = ANY(:slugs)"),
        {"slugs": [item[1] for item in STORY_PERMISSIONS]},
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
    """Удаляет story permissions и их связи с ролями."""
    connection = op.get_bind()
    slugs = [item[1] for item in STORY_PERMISSIONS]

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

    connection.execute(
        sa.text("DELETE FROM permissions WHERE slug = ANY(:slugs)"),
        {"slugs": slugs},
    )
