from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy import event
from sqlalchemy.orm import object_session

from app.audit_context import get_audit_actor_user_id
from app.audit_service import (
    AUDIT_TRACKED_MODELS,
    build_audit_snapshot,
    build_before_snapshot_for_update,
    sanitize_snapshot_for_storage,
)
from app.models import ChangeLog, User


_EVENT_LISTENERS_REGISTERED = False


def register_audit_event_listeners() -> None:
    """Регистрирует слушатели SQLAlchemy для автоматического audit-логирования."""
    global _EVENT_LISTENERS_REGISTERED
    if _EVENT_LISTENERS_REGISTERED:
        return

    for model_class in AUDIT_TRACKED_MODELS:
        event.listen(model_class, "after_insert", _after_insert_listener)
        event.listen(model_class, "after_update", _after_update_listener)
        event.listen(model_class, "before_delete", _before_delete_listener)

    _EVENT_LISTENERS_REGISTERED = True


def _after_insert_listener(_: Any, connection: Connection, target: object) -> None:
    entity_type = _resolve_entity_type(target)
    entity_id = _resolve_entity_id(target)
    actor_user_id = _resolve_actor_user_id(connection, target)

    after_snapshot = sanitize_snapshot_for_storage(build_audit_snapshot(target))
    _insert_change_log(
        connection=connection,
        entity_type=entity_type,
        entity_id=entity_id,
        before_snapshot={},
        after_snapshot=after_snapshot,
        created_by=actor_user_id,
    )


def _after_update_listener(_: Any, connection: Connection, target: object) -> None:
    entity_type = _resolve_entity_type(target)
    entity_id = _resolve_entity_id(target)
    actor_user_id = _resolve_actor_user_id(connection, target)

    after_snapshot = sanitize_snapshot_for_storage(build_audit_snapshot(target))
    before_snapshot = sanitize_snapshot_for_storage(
        build_before_snapshot_for_update(target, after_snapshot)
    )

    if before_snapshot == after_snapshot:
        return

    _insert_change_log(
        connection=connection,
        entity_type=entity_type,
        entity_id=entity_id,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        created_by=actor_user_id,
    )


def _before_delete_listener(_: Any, connection: Connection, target: object) -> None:
    entity_type = _resolve_entity_type(target)
    entity_id = _resolve_entity_id(target)
    actor_user_id = _resolve_actor_user_id(connection, target)

    before_snapshot = sanitize_snapshot_for_storage(build_audit_snapshot(target))

    _insert_change_log(
        connection=connection,
        entity_type=entity_type,
        entity_id=entity_id,
        before_snapshot=before_snapshot,
        after_snapshot={},
        created_by=actor_user_id,
    )


def _resolve_entity_type(target: object) -> str:
    for model_class, entity_type in AUDIT_TRACKED_MODELS.items():
        if isinstance(target, model_class):
            return entity_type

    raise ValueError("Аудит-логирование не поддерживается для переданного типа сущности.")


def _resolve_entity_id(target: object) -> int:
    entity_id = getattr(target, "id", None)
    if entity_id is None:
        raise ValueError("Невозможно записать audit-log: отсутствует id сущности.")
    return int(entity_id)


def _resolve_actor_user_id(connection: Connection, target: object) -> int:
    session = object_session(target)
    actor_from_session = get_audit_actor_user_id(session)
    if actor_from_session is not None:
        return actor_from_session

    fallback_from_created_by = getattr(target, "created_by", None)
    if fallback_from_created_by is not None:
        return int(fallback_from_created_by)

    if isinstance(target, User):
        first_user_id = connection.execute(select(User.id).order_by(User.id.asc()).limit(1)).scalar()
        if first_user_id is not None:
            return int(first_user_id)

        target_id = getattr(target, "id", None)
        if target_id is not None:
            return int(target_id)

    raise ValueError("Невозможно определить created_by для audit-log: users пусты.")


def _insert_change_log(
    connection: Connection,
    entity_type: str,
    entity_id: int,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    created_by: int,
) -> None:
    connection.execute(
        ChangeLog.__table__.insert().values(
            entity_type=entity_type,
            entity_id=entity_id,
            before=before_snapshot,
            after=after_snapshot,
            created_by=created_by,
        )
    )
