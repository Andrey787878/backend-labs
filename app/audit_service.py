from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit_context import bind_audit_actor
from app.dto import ChangeLogCollectionDTO, ChangeLogDTO, ChangedFieldDTO
from app.models import ChangeLog, Permission, Role, User


AUDIT_ENTITY_USER = "user"
AUDIT_ENTITY_ROLE = "role"
AUDIT_ENTITY_PERMISSION = "permission"

AUDIT_TRACKED_MODELS = {
    User: AUDIT_ENTITY_USER,
    Role: AUDIT_ENTITY_ROLE,
    Permission: AUDIT_ENTITY_PERMISSION,
}

AUDIT_SECRET_FIELDS = {"password_hash"}


class AuditServiceError(Exception):
    """Базовое исключение audit-сервиса."""


class AuditNotFoundError(AuditServiceError):
    """Запись аудита или целевая сущность не найдена."""


class AuditConflictError(AuditServiceError):
    """Конфликт данных при восстановлении из аудита."""


class AuditPersistenceError(AuditServiceError):
    """Ошибка сохранения данных аудита."""


class AuditService:
    """Сервис истории изменений и восстановления состояния сущностей."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_user_story(self, user_id: int) -> ChangeLogCollectionDTO:
        """Возвращает историю изменений пользователя."""
        return self._list_story(
            entity_type=AUDIT_ENTITY_USER,
            entity_id=user_id,
            not_found_message="История изменений пользователя не найдена.",
        )

    def list_role_story(self, role_id: int) -> ChangeLogCollectionDTO:
        """Возвращает историю изменений роли."""
        return self._list_story(
            entity_type=AUDIT_ENTITY_ROLE,
            entity_id=role_id,
            not_found_message="История изменений роли не найдена.",
        )

    def list_permission_story(self, permission_id: int) -> ChangeLogCollectionDTO:
        """Возвращает историю изменений разрешения."""
        return self._list_story(
            entity_type=AUDIT_ENTITY_PERMISSION,
            entity_id=permission_id,
            not_found_message="История изменений разрешения не найдена.",
        )

    def restore_from_log(self, log_id: int, actor_user_id: int) -> ChangeLogDTO:
        """Восстанавливает состояние сущности по состоянию before выбранного лога."""
        self._require_user(actor_user_id, include_deleted=False)
        log = self._require_log(log_id)

        with bind_audit_actor(self._db, actor_user_id):
            if log.entity_type == AUDIT_ENTITY_USER:
                restored = self._restore_user(log)
            elif log.entity_type == AUDIT_ENTITY_ROLE:
                restored = self._restore_role(log)
            elif log.entity_type == AUDIT_ENTITY_PERMISSION:
                restored = self._restore_permission(log)
            else:
                raise AuditConflictError("Неподдерживаемый тип сущности в change log.")

            self._commit_or_rollback()

        if restored is None:
            raise AuditNotFoundError("Не удалось определить запись восстановления аудита.")

        return self._to_log_dto(restored)

    def get_log(self, log_id: int) -> ChangeLog:
        """Возвращает запись лога по id."""
        return self._require_log(log_id)

    def _restore_user(self, log: ChangeLog) -> ChangeLog | None:
        before_state = dict(log.before or {})
        after_state = dict(log.after or {})

        if not before_state and after_state:
            # До мутации записи не существовало -> откат creation = удалить запись.
            user = self._db.get(User, log.entity_id)
            if user is None:
                return log
            self._db.delete(user)
            self._db.flush()
            return self._latest_entity_log(AUDIT_ENTITY_USER, log.entity_id)

        target = self._db.get(User, log.entity_id)
        if target is None:
            if not before_state:
                raise AuditNotFoundError("Состояние для восстановления пользователя пустое.")
            password_hash = before_state.get("password_hash")
            if not password_hash:
                raise AuditConflictError(
                    "Невозможно восстановить физически удаленного пользователя: "
                    "password_hash не хранится в audit-log в целях безопасности."
                )
            target = User(
                id=int(before_state.get("id", log.entity_id)),
                username=str(before_state["username"]),
                email=str(before_state["email"]),
                password_hash=str(password_hash),
                birthday=_parse_date(before_state["birthday"]),
            )
            self._db.add(target)
            self._db.flush()

        # Восстановление мягко удаленного пользователя.
        if _user_matches_before_state(target, before_state):
            return log

        target.deleted_at = None
        target.deleted_by = None
        self._apply_user_state(target, before_state)
        self._db.flush()
        return self._latest_entity_log(AUDIT_ENTITY_USER, target.id)

    def _restore_role(self, log: ChangeLog) -> ChangeLog | None:
        before_state = dict(log.before or {})
        after_state = dict(log.after or {})

        if not before_state and after_state:
            role = self._db.get(Role, log.entity_id)
            if role is None:
                return log
            self._db.delete(role)
            self._db.flush()
            return self._latest_entity_log(AUDIT_ENTITY_ROLE, log.entity_id)

        target = self._db.get(Role, log.entity_id)
        if target is None:
            if not before_state:
                raise AuditNotFoundError("Состояние для восстановления роли пустое.")
            target = Role(
                id=int(before_state.get("id", log.entity_id)),
                name=str(before_state["name"]),
                slug=str(before_state["slug"]),
                description=_none_or_str(before_state.get("description")),
                created_by=int(before_state["created_by"]),
            )
            self._db.add(target)
            self._db.flush()

        if _role_matches_before_state(target, before_state):
            return log

        target.deleted_at = None
        target.deleted_by = None
        self._apply_role_state(target, before_state)
        self._db.flush()
        return self._latest_entity_log(AUDIT_ENTITY_ROLE, target.id)

    def _restore_permission(self, log: ChangeLog) -> ChangeLog | None:
        before_state = dict(log.before or {})
        after_state = dict(log.after or {})

        if not before_state and after_state:
            permission = self._db.get(Permission, log.entity_id)
            if permission is None:
                return log
            self._db.delete(permission)
            self._db.flush()
            return self._latest_entity_log(AUDIT_ENTITY_PERMISSION, log.entity_id)

        target = self._db.get(Permission, log.entity_id)
        if target is None:
            if not before_state:
                raise AuditNotFoundError("Состояние для восстановления разрешения пустое.")
            target = Permission(
                id=int(before_state.get("id", log.entity_id)),
                name=str(before_state["name"]),
                slug=str(before_state["slug"]),
                description=_none_or_str(before_state.get("description")),
                created_by=int(before_state["created_by"]),
            )
            self._db.add(target)
            self._db.flush()

        if _permission_matches_before_state(target, before_state):
            return log

        target.deleted_at = None
        target.deleted_by = None
        self._apply_permission_state(target, before_state)
        self._db.flush()
        return self._latest_entity_log(AUDIT_ENTITY_PERMISSION, target.id)

    def _apply_user_state(self, target: User, before_state: dict[str, Any]) -> None:
        if "username" in before_state:
            target.username = str(before_state["username"])
        if "email" in before_state:
            target.email = str(before_state["email"])
        if "birthday" in before_state:
            target.birthday = _parse_date(before_state["birthday"])
        # Совместимость со старыми audit-log записями; новые snapshot-ы password_hash не хранят.
        if "password_hash" in before_state:
            target.password_hash = str(before_state["password_hash"])
        target.updated_at = self._now_utc()

    def _apply_role_state(self, target: Role, before_state: dict[str, Any]) -> None:
        if "name" in before_state:
            target.name = str(before_state["name"])
        if "slug" in before_state:
            target.slug = str(before_state["slug"])
        if "description" in before_state:
            target.description = _none_or_str(before_state.get("description"))
        target.updated_at = self._now_utc()

    def _apply_permission_state(self, target: Permission, before_state: dict[str, Any]) -> None:
        if "name" in before_state:
            target.name = str(before_state["name"])
        if "slug" in before_state:
            target.slug = str(before_state["slug"])
        if "description" in before_state:
            target.description = _none_or_str(before_state.get("description"))
        target.updated_at = self._now_utc()

    def _list_story(
        self,
        entity_type: str,
        entity_id: int,
        not_found_message: str,
    ) -> ChangeLogCollectionDTO:
        logs = list(
            self._db.scalars(
                select(ChangeLog)
                .where(
                    ChangeLog.entity_type == entity_type,
                    ChangeLog.entity_id == entity_id,
                )
                .order_by(ChangeLog.created_at.asc(), ChangeLog.id.asc())
            )
        )
        if not logs:
            raise AuditNotFoundError(not_found_message)
        items = [self._to_log_dto(log) for log in logs]
        return ChangeLogCollectionDTO(items=items, total=len(items))

    def _require_log(self, log_id: int) -> ChangeLog:
        log = self._db.get(ChangeLog, log_id)
        if log is None:
            raise AuditNotFoundError("Запись change log не найдена.")
        return log

    def _latest_entity_log(self, entity_type: str, entity_id: int) -> ChangeLog | None:
        return self._db.scalar(
            select(ChangeLog)
            .where(
                ChangeLog.entity_type == entity_type,
                ChangeLog.entity_id == entity_id,
            )
            .order_by(ChangeLog.id.desc())
        )

    def _require_user(self, user_id: int, *, include_deleted: bool) -> User:
        stmt = select(User).where(User.id == user_id)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))

        user = self._db.scalar(stmt)
        if user is None:
            raise AuditNotFoundError("Пользователь не найден.")
        return user

    def _require_role(self, role_id: int, *, include_deleted: bool) -> Role:
        stmt = select(Role).where(Role.id == role_id)
        if not include_deleted:
            stmt = stmt.where(Role.deleted_at.is_(None))

        role = self._db.scalar(stmt)
        if role is None:
            raise AuditNotFoundError("Роль не найдена.")
        return role

    def _require_permission(self, permission_id: int, *, include_deleted: bool) -> Permission:
        stmt = select(Permission).where(Permission.id == permission_id)
        if not include_deleted:
            stmt = stmt.where(Permission.deleted_at.is_(None))

        permission = self._db.scalar(stmt)
        if permission is None:
            raise AuditNotFoundError("Разрешение не найдено.")
        return permission

    def _commit_or_rollback(self) -> None:
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise AuditConflictError("Конфликт данных при восстановлении из истории.") from exc
        except SQLAlchemyError as exc:
            self._db.rollback()
            raise AuditPersistenceError("Ошибка сохранения данных аудита.") from exc

    @staticmethod
    def _to_log_dto(log: ChangeLog) -> ChangeLogDTO:
        changed_fields: dict[str, ChangedFieldDTO] = {}
        before = log.before or {}
        after = log.after or {}
        for key in sorted(set(before.keys()) | set(after.keys())):
            if key in AUDIT_SECRET_FIELDS:
                continue
            old_value = before.get(key)
            new_value = after.get(key)
            if old_value != new_value:
                changed_fields[key] = ChangedFieldDTO(old=old_value, new=new_value)

        return ChangeLogDTO(
            id=log.id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            changed_fields=changed_fields,
            created_at=log.created_at,
            created_by=log.created_by,
        )

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)


def build_audit_snapshot(target: object) -> dict[str, Any]:
    """Строит сериализуемый срез column-атрибутов модели для change_logs."""
    state = inspect(target)
    snapshot: dict[str, Any] = {}
    for column_attr in state.mapper.column_attrs:
        key = column_attr.key
        value = getattr(target, key)
        snapshot[key] = _serialize_audit_value(value)
    return snapshot


def build_before_snapshot_for_update(target: object, after_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Восстанавливает значения ДО обновления по истории атрибутов SQLAlchemy."""
    state = inspect(target)
    before_snapshot = dict(after_snapshot)
    for column_attr in state.mapper.column_attrs:
        key = column_attr.key
        history = state.attrs[key].history
        if not history.has_changes():
            continue

        if history.deleted:
            before_snapshot[key] = _serialize_audit_value(history.deleted[0])
            continue

        if history.unchanged:
            before_snapshot[key] = _serialize_audit_value(history.unchanged[0])
            continue

        # Если deleted/unchanged отсутствуют, предыдущего значения у ORM нет.
        # Оставляем в before текущее after-значение как best-effort fallback.

    return before_snapshot


def sanitize_snapshot_for_storage(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Подготавливает snapshot к сохранению в change_logs."""
    return {
        key: value
        for key, value in snapshot.items()
        if key not in AUDIT_SECRET_FIELDS
    }


def _user_matches_before_state(target: User, before_state: dict[str, Any]) -> bool:
    """Проверяет, находится ли пользователь уже в состоянии before."""
    if target.deleted_at is not None or target.deleted_by is not None:
        return False
    if "username" in before_state and target.username != str(before_state["username"]):
        return False
    if "email" in before_state and target.email != str(before_state["email"]):
        return False
    if "birthday" in before_state and target.birthday != _parse_date(before_state["birthday"]):
        return False
    if "password_hash" in before_state and target.password_hash != str(before_state["password_hash"]):
        return False
    return True


def _role_matches_before_state(target: Role, before_state: dict[str, Any]) -> bool:
    """Проверяет, находится ли роль уже в состоянии before."""
    if target.deleted_at is not None or target.deleted_by is not None:
        return False
    if "name" in before_state and target.name != str(before_state["name"]):
        return False
    if "slug" in before_state and target.slug != str(before_state["slug"]):
        return False
    if "description" in before_state and target.description != _none_or_str(
        before_state.get("description")
    ):
        return False
    return True


def _permission_matches_before_state(target: Permission, before_state: dict[str, Any]) -> bool:
    """Проверяет, находится ли разрешение уже в состоянии before."""
    if target.deleted_at is not None or target.deleted_by is not None:
        return False
    if "name" in before_state and target.name != str(before_state["name"]):
        return False
    if "slug" in before_state and target.slug != str(before_state["slug"]):
        return False
    if "description" in before_state and target.description != _none_or_str(
        before_state.get("description")
    ):
        return False
    return True


def _serialize_audit_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise AuditConflictError("Некорректное значение даты в состоянии истории.")


def _none_or_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
