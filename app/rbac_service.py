from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.audit_context import bind_audit_actor
from app.dto import (
    PermissionCollectionDTO,
    PermissionDTO,
    PermissionUpdateDTO,
    PermissionWriteDTO,
    RoleCollectionDTO,
    RoleDTO,
    RoleUpdateDTO,
    RoleWriteDTO,
    UserUpdateDTO,
    UserDTO,
)
from app.models import Permission, PermissionRole, Role, User, UserRole


class RbacServiceError(Exception):
    """Базовое исключение RBAC-сервиса."""


class RbacNotFoundError(RbacServiceError):
    """Искомая RBAC-сущность не найдена."""


class RbacConflictError(RbacServiceError):
    """Конфликт данных RBAC."""


class RbacPersistenceError(RbacServiceError):
    """Ошибка сохранения RBAC-данных."""


class RbacUserNotFoundError(RbacNotFoundError):
    """Пользователь не найден."""


class RoleNotFoundError(RbacNotFoundError):
    """Роль не найдена."""


class PermissionNotFoundError(RbacNotFoundError):
    """Разрешение не найдено."""


class UserRoleNotFoundError(RbacNotFoundError):
    """Связь пользователь-роль не найдена."""


class PermissionRoleNotFoundError(RbacNotFoundError):
    """Связь роль-разрешение не найдена."""


class RoleAlreadyExistsError(RbacConflictError):
    """Роль с таким именем или slug уже существует."""


class PermissionAlreadyExistsError(RbacConflictError):
    """Разрешение с таким именем или slug уже существует."""


class UserRoleAlreadyExistsError(RbacConflictError):
    """Активная связь пользователь-роль уже существует."""


class PermissionRoleAlreadyExistsError(RbacConflictError):
    """Активная связь роль-разрешение уже существует."""


class UserAlreadyExistsError(RbacConflictError):
    """Пользователь с таким username или email уже существует."""


class RbacService:
    """Бизнес-логика управления ролями, разрешениями и их связями."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_users(self) -> list[UserDTO]:
        """Возвращает всех пользователей с активными ролями."""
        users = list(
            self._db.scalars(
                select(User)
                .options(selectinload(User.roles))
                .where(User.deleted_at.is_(None))
                .order_by(User.id.asc())
            )
        )
        return [self._to_user_dto(user) for user in users]

    def get_user(self, user_id: int) -> UserDTO:
        """Возвращает активного пользователя по id."""
        return self._to_user_dto(self._require_user(user_id, include_deleted=False))

    def update_user_patch(self, user_id: int, data: UserUpdateDTO, actor_user_id: int) -> UserDTO:
        """Частично обновляет пользователя администратором."""
        self._require_user(actor_user_id, include_deleted=False)
        user = self._require_user(user_id, include_deleted=False)

        changed = False
        with bind_audit_actor(self._db, actor_user_id):
            if data.has_username:
                if data.username is None:
                    raise ValueError("username не должен быть null.")
                normalized_username = data.username.strip()
                if self._username_exists(normalized_username, exclude_user_id=user_id):
                    raise UserAlreadyExistsError("Пользователь с таким username уже существует.")
                user.username = normalized_username
                changed = True

            if data.has_email:
                if data.email is None:
                    raise ValueError("email не должен быть null.")
                normalized_email = data.email.strip()
                if self._email_exists(normalized_email, exclude_user_id=user_id):
                    raise UserAlreadyExistsError("Пользователь с таким email уже существует.")
                user.email = normalized_email
                changed = True

            if data.has_birthday:
                if data.birthday is None:
                    raise ValueError("birthday не должен быть null.")
                user.birthday = data.birthday
                changed = True

            if not changed:
                raise ValueError("Хотя бы одно поле для обновления должно быть передано.")

            user.updated_at = self._now_utc()
            self._commit_or_rollback(
                integrity_error=UserAlreadyExistsError(
                    "Пользователь с таким username или email уже существует."
                ),
            )

        self._db.refresh(user)
        return self._to_user_dto(user)

    def hard_delete_user(self, user_id: int, actor_user_id: int) -> None:
        """Физически удаляет пользователя."""
        self._require_user(actor_user_id, include_deleted=False)
        user = self._require_user(user_id, include_deleted=True)

        with bind_audit_actor(self._db, actor_user_id):
            self._db.delete(user)
            self._commit_or_rollback(
                integrity_error=RbacConflictError(
                    "Невозможно выполнить hard-delete пользователя: есть связанные записи."
                ),
            )

    def soft_delete_user(self, user_id: int, actor_user_id: int) -> None:
        """Мягко удаляет активного пользователя."""
        self._require_user(actor_user_id, include_deleted=False)
        user = self._require_user(user_id, include_deleted=False)

        with bind_audit_actor(self._db, actor_user_id):
            user.deleted_at = self._now_utc()
            user.deleted_by = actor_user_id
            user.updated_at = self._now_utc()
            self._commit_or_rollback()

    def restore_user(self, user_id: int, actor_user_id: int) -> None:
        """Восстанавливает мягко удаленного пользователя."""
        self._require_user(actor_user_id, include_deleted=False)
        user = self._db.scalar(
            select(User).where(
                User.id == user_id,
                User.deleted_at.is_not(None),
            )
        )
        if user is None:
            raise RbacUserNotFoundError("Мягко удалённый пользователь не найден.")

        with bind_audit_actor(self._db, actor_user_id):
            user.deleted_at = None
            user.deleted_by = None
            user.updated_at = self._now_utc()
            self._commit_or_rollback()

    def list_user_active_roles(self, user_id: int) -> RoleCollectionDTO:
        """Возвращает список активных ролей пользователя."""
        self._require_user(user_id)

        roles = list(
            self._db.scalars(
                select(Role)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(
                    UserRole.user_id == user_id,
                    UserRole.deleted_at.is_(None),
                    Role.deleted_at.is_(None),
                )
                .order_by(Role.id.asc())
            )
        )

        items = [self._to_role_dto(role) for role in roles]
        return RoleCollectionDTO(items=items, total=len(items))

    def attach_user_role(self, user_id: int, role_id: int, actor_user_id: int) -> RoleDTO:
        """Назначает роль пользователю или восстанавливает мягко удалённую связь."""
        self._require_user(actor_user_id)
        self._require_user(user_id)
        role = self._require_role(role_id, include_deleted=False)

        link = self._db.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
            )
        )

        if link is None:
            self._db.add(
                UserRole(
                    user_id=user_id,
                    role_id=role_id,
                    created_by=actor_user_id,
                )
            )
            self._commit_or_rollback(
                integrity_error=UserRoleAlreadyExistsError("У пользователя уже есть такая активная роль."),
            )
            return self._to_role_dto(role)

        if link.deleted_at is None:
            raise UserRoleAlreadyExistsError("У пользователя уже есть такая активная роль.")

        link.deleted_at = None
        link.deleted_by = None
        self._commit_or_rollback()
        return self._to_role_dto(role)

    def hard_delete_user_role(self, user_id: int, role_id: int) -> None:
        """Физически удаляет связь пользователь-роль."""
        self._require_user(user_id)
        self._require_role(role_id, include_deleted=True)
        link = self._require_user_role_link(user_id, role_id)

        self._db.delete(link)
        self._commit_or_rollback()

    def soft_delete_user_role(self, user_id: int, role_id: int, actor_user_id: int) -> None:
        """Мягко удаляет активную связь пользователь-роль."""
        self._require_user(actor_user_id)
        self._require_user(user_id)
        self._require_role(role_id, include_deleted=True)
        link = self._require_active_user_role_link(user_id, role_id)

        link.deleted_at = self._now_utc()
        link.deleted_by = actor_user_id
        self._commit_or_rollback()

    def restore_user_role(self, user_id: int, role_id: int) -> None:
        """Восстанавливает мягко удалённую связь пользователь-роль."""
        self._require_user(user_id)
        role = self._require_role(role_id, include_deleted=True)
        if role.deleted_at is not None:
            raise RoleNotFoundError("Нельзя восстановить связь с мягко удалённой ролью.")

        link = self._require_deleted_user_role_link(user_id, role_id)
        link.deleted_at = None
        link.deleted_by = None
        self._commit_or_rollback()

    def list_roles(self) -> RoleCollectionDTO:
        """Возвращает список активных ролей."""
        roles = list(
            self._db.scalars(
                select(Role)
                .where(Role.deleted_at.is_(None))
                .order_by(Role.id.asc())
            )
        )
        items = [self._to_role_dto(role) for role in roles]
        return RoleCollectionDTO(items=items, total=len(items))

    def get_role(self, role_id: int) -> RoleDTO:
        """Возвращает активную роль по id."""
        return self._to_role_dto(self._require_role(role_id, include_deleted=False))

    def create_role(self, data: RoleWriteDTO, actor_user_id: int) -> RoleDTO:
        """Создаёт роль."""
        self._require_user(actor_user_id, include_deleted=False)

        name = data.name.strip()
        slug = data.slug.strip()
        if self._role_name_exists(name):
            raise RoleAlreadyExistsError("Роль с таким name уже существует.")
        if self._role_slug_exists(slug):
            raise RoleAlreadyExistsError("Роль с таким slug уже существует.")

        with bind_audit_actor(self._db, actor_user_id):
            role = Role(
                name=name,
                slug=slug,
                description=data.description,
                created_by=actor_user_id,
            )
            self._db.add(role)
            self._commit_or_rollback(
                integrity_error=RoleAlreadyExistsError("Роль с таким name или slug уже существует."),
            )
        self._db.refresh(role)
        return self._to_role_dto(role)

    def update_role_put(self, role_id: int, data: RoleWriteDTO, actor_user_id: int) -> RoleDTO:
        """Полностью обновляет роль (PUT)."""
        self._require_user(actor_user_id, include_deleted=False)
        role = self._require_role(role_id, include_deleted=False)

        normalized_name = data.name.strip()
        normalized_slug = data.slug.strip()
        if self._role_name_exists(normalized_name, exclude_role_id=role_id):
            raise RoleAlreadyExistsError("Роль с таким name уже существует.")
        if self._role_slug_exists(normalized_slug, exclude_role_id=role_id):
            raise RoleAlreadyExistsError("Роль с таким slug уже существует.")

        with bind_audit_actor(self._db, actor_user_id):
            role.name = normalized_name
            role.slug = normalized_slug
            role.description = data.description
            role.updated_at = self._now_utc()

            self._commit_or_rollback(
                integrity_error=RoleAlreadyExistsError("Роль с таким name или slug уже существует."),
            )
        self._db.refresh(role)
        return self._to_role_dto(role)

    def update_role_patch(self, role_id: int, data: RoleUpdateDTO, actor_user_id: int) -> RoleDTO:
        """Частично обновляет роль (PATCH)."""
        self._require_user(actor_user_id, include_deleted=False)
        role = self._require_role(role_id, include_deleted=False)

        with bind_audit_actor(self._db, actor_user_id):
            changed = False
            if data.has_name:
                if data.name is None:
                    raise ValueError("name не должен быть null.")
                normalized_name = data.name.strip()
                if self._role_name_exists(normalized_name, exclude_role_id=role_id):
                    raise RoleAlreadyExistsError("Роль с таким name уже существует.")
                role.name = normalized_name
                changed = True

            if data.has_slug:
                if data.slug is None:
                    raise ValueError("slug не должен быть null.")
                normalized_slug = data.slug.strip()
                if self._role_slug_exists(normalized_slug, exclude_role_id=role_id):
                    raise RoleAlreadyExistsError("Роль с таким slug уже существует.")
                role.slug = normalized_slug
                changed = True

            if data.has_description:
                role.description = data.description
                changed = True

            if not changed:
                raise ValueError("Хотя бы одно поле для обновления должно быть передано.")

            role.updated_at = self._now_utc()
            self._commit_or_rollback(
                integrity_error=RoleAlreadyExistsError("Роль с таким name или slug уже существует."),
            )
        self._db.refresh(role)
        return self._to_role_dto(role)

    def hard_delete_role(self, role_id: int, actor_user_id: int) -> None:
        """Физически удаляет роль."""
        self._require_user(actor_user_id, include_deleted=False)
        role = self._require_role(role_id, include_deleted=True)
        with bind_audit_actor(self._db, actor_user_id):
            self._db.delete(role)
            self._commit_or_rollback(
                integrity_error=RbacConflictError(
                    "Невозможно выполнить hard-delete роли: есть связанные записи."
                ),
            )

    def soft_delete_role(self, role_id: int, actor_user_id: int) -> None:
        """Мягко удаляет активную роль."""
        self._require_user(actor_user_id, include_deleted=False)
        role = self._require_role(role_id, include_deleted=False)

        with bind_audit_actor(self._db, actor_user_id):
            role.deleted_at = self._now_utc()
            role.deleted_by = actor_user_id
            role.updated_at = self._now_utc()
            self._commit_or_rollback()

    def restore_role(self, role_id: int, actor_user_id: int) -> None:
        """Восстанавливает мягко удалённую роль."""
        self._require_user(actor_user_id, include_deleted=False)
        role = self._db.scalar(
            select(Role).where(
                Role.id == role_id,
                Role.deleted_at.is_not(None),
            )
        )
        if role is None:
            raise RoleNotFoundError("Мягко удалённая роль не найдена.")

        with bind_audit_actor(self._db, actor_user_id):
            role.deleted_at = None
            role.deleted_by = None
            role.updated_at = self._now_utc()
            self._commit_or_rollback()

    def list_permissions(self) -> PermissionCollectionDTO:
        """Возвращает список активных разрешений."""
        permissions = list(
            self._db.scalars(
                select(Permission)
                .where(Permission.deleted_at.is_(None))
                .order_by(Permission.id.asc())
            )
        )
        items = [self._to_permission_dto(permission) for permission in permissions]
        return PermissionCollectionDTO(items=items, total=len(items))

    def get_permission(self, permission_id: int) -> PermissionDTO:
        """Возвращает активное разрешение по id."""
        return self._to_permission_dto(
            self._require_permission(permission_id, include_deleted=False)
        )

    def create_permission(self, data: PermissionWriteDTO, actor_user_id: int) -> PermissionDTO:
        """Создаёт разрешение."""
        self._require_user(actor_user_id, include_deleted=False)

        name = data.name.strip()
        slug = data.slug.strip()
        if self._permission_name_exists(name):
            raise PermissionAlreadyExistsError("Разрешение с таким name уже существует.")
        if self._permission_slug_exists(slug):
            raise PermissionAlreadyExistsError("Разрешение с таким slug уже существует.")

        with bind_audit_actor(self._db, actor_user_id):
            permission = Permission(
                name=name,
                slug=slug,
                description=data.description,
                created_by=actor_user_id,
            )
            self._db.add(permission)
            self._commit_or_rollback(
                integrity_error=PermissionAlreadyExistsError(
                    "Разрешение с таким name или slug уже существует."
                )
            )
        self._db.refresh(permission)
        return self._to_permission_dto(permission)

    def update_permission_put(
        self,
        permission_id: int,
        data: PermissionWriteDTO,
        actor_user_id: int,
    ) -> PermissionDTO:
        """Полностью обновляет разрешение (PUT)."""
        self._require_user(actor_user_id, include_deleted=False)
        permission = self._require_permission(permission_id, include_deleted=False)

        normalized_name = data.name.strip()
        normalized_slug = data.slug.strip()
        if self._permission_name_exists(normalized_name, exclude_permission_id=permission_id):
            raise PermissionAlreadyExistsError("Разрешение с таким name уже существует.")
        if self._permission_slug_exists(normalized_slug, exclude_permission_id=permission_id):
            raise PermissionAlreadyExistsError("Разрешение с таким slug уже существует.")

        with bind_audit_actor(self._db, actor_user_id):
            permission.name = normalized_name
            permission.slug = normalized_slug
            permission.description = data.description
            permission.updated_at = self._now_utc()

            self._commit_or_rollback(
                integrity_error=PermissionAlreadyExistsError(
                    "Разрешение с таким name или slug уже существует."
                )
            )
        self._db.refresh(permission)
        return self._to_permission_dto(permission)

    def update_permission_patch(
        self,
        permission_id: int,
        data: PermissionUpdateDTO,
        actor_user_id: int,
    ) -> PermissionDTO:
        """Частично обновляет разрешение (PATCH)."""
        self._require_user(actor_user_id, include_deleted=False)
        permission = self._require_permission(permission_id, include_deleted=False)

        with bind_audit_actor(self._db, actor_user_id):
            changed = False
            if data.has_name:
                if data.name is None:
                    raise ValueError("name не должен быть null.")
                normalized_name = data.name.strip()
                if self._permission_name_exists(normalized_name, exclude_permission_id=permission_id):
                    raise PermissionAlreadyExistsError("Разрешение с таким name уже существует.")
                permission.name = normalized_name
                changed = True

            if data.has_slug:
                if data.slug is None:
                    raise ValueError("slug не должен быть null.")
                normalized_slug = data.slug.strip()
                if self._permission_slug_exists(normalized_slug, exclude_permission_id=permission_id):
                    raise PermissionAlreadyExistsError("Разрешение с таким slug уже существует.")
                permission.slug = normalized_slug
                changed = True

            if data.has_description:
                permission.description = data.description
                changed = True

            if not changed:
                raise ValueError("Хотя бы одно поле для обновления должно быть передано.")

            permission.updated_at = self._now_utc()
            self._commit_or_rollback(
                integrity_error=PermissionAlreadyExistsError(
                    "Разрешение с таким name или slug уже существует."
                )
            )
        self._db.refresh(permission)
        return self._to_permission_dto(permission)

    def hard_delete_permission(self, permission_id: int, actor_user_id: int) -> None:
        """Физически удаляет разрешение."""
        self._require_user(actor_user_id, include_deleted=False)
        permission = self._require_permission(permission_id, include_deleted=True)
        with bind_audit_actor(self._db, actor_user_id):
            self._db.delete(permission)
            self._commit_or_rollback(
                integrity_error=RbacConflictError(
                    "Невозможно выполнить hard-delete разрешения: есть связанные записи."
                ),
            )

    def soft_delete_permission(self, permission_id: int, actor_user_id: int) -> None:
        """Мягко удаляет активное разрешение."""
        self._require_user(actor_user_id, include_deleted=False)
        permission = self._require_permission(permission_id, include_deleted=False)

        with bind_audit_actor(self._db, actor_user_id):
            permission.deleted_at = self._now_utc()
            permission.deleted_by = actor_user_id
            permission.updated_at = self._now_utc()
            self._commit_or_rollback()

    def restore_permission(self, permission_id: int, actor_user_id: int) -> None:
        """Восстанавливает мягко удалённое разрешение."""
        self._require_user(actor_user_id, include_deleted=False)
        permission = self._db.scalar(
            select(Permission).where(
                Permission.id == permission_id,
                Permission.deleted_at.is_not(None),
            )
        )
        if permission is None:
            raise PermissionNotFoundError("Мягко удалённое разрешение не найдено.")

        with bind_audit_actor(self._db, actor_user_id):
            permission.deleted_at = None
            permission.deleted_by = None
            permission.updated_at = self._now_utc()
            self._commit_or_rollback()

    def list_role_active_permissions(self, role_id: int) -> PermissionCollectionDTO:
        """Возвращает список активных разрешений роли."""
        self._require_role(role_id, include_deleted=False)

        permissions = list(
            self._db.scalars(
                select(Permission)
                .join(PermissionRole, PermissionRole.permission_id == Permission.id)
                .where(
                    PermissionRole.role_id == role_id,
                    PermissionRole.deleted_at.is_(None),
                    Permission.deleted_at.is_(None),
                )
                .order_by(Permission.id.asc())
            )
        )

        items = [self._to_permission_dto(permission) for permission in permissions]
        return PermissionCollectionDTO(items=items, total=len(items))

    def attach_role_permission(
        self,
        role_id: int,
        permission_id: int,
        actor_user_id: int,
    ) -> PermissionDTO:
        """Назначает разрешение роли или восстанавливает мягко удалённую связь."""
        self._require_user(actor_user_id)
        self._require_role(role_id, include_deleted=False)
        permission = self._require_permission(permission_id, include_deleted=False)

        link = self._db.scalar(
            select(PermissionRole).where(
                PermissionRole.role_id == role_id,
                PermissionRole.permission_id == permission_id,
            )
        )

        if link is None:
            self._db.add(
                PermissionRole(
                    role_id=role_id,
                    permission_id=permission_id,
                    created_by=actor_user_id,
                )
            )
            self._commit_or_rollback(
                integrity_error=PermissionRoleAlreadyExistsError(
                    "У роли уже есть такое активное разрешение."
                )
            )
            return self._to_permission_dto(permission)

        if link.deleted_at is None:
            raise PermissionRoleAlreadyExistsError("У роли уже есть такое активное разрешение.")

        link.deleted_at = None
        link.deleted_by = None
        self._commit_or_rollback()
        return self._to_permission_dto(permission)

    def hard_delete_role_permission(self, role_id: int, permission_id: int) -> None:
        """Физически удаляет связь роль-разрешение."""
        self._require_role(role_id, include_deleted=True)
        self._require_permission(permission_id, include_deleted=True)
        link = self._require_permission_role_link(role_id, permission_id)

        self._db.delete(link)
        self._commit_or_rollback()

    def soft_delete_role_permission(
        self,
        role_id: int,
        permission_id: int,
        actor_user_id: int,
    ) -> None:
        """Мягко удаляет активную связь роль-разрешение."""
        self._require_user(actor_user_id)
        self._require_role(role_id, include_deleted=True)
        self._require_permission(permission_id, include_deleted=True)
        link = self._require_active_permission_role_link(role_id, permission_id)

        link.deleted_at = self._now_utc()
        link.deleted_by = actor_user_id
        self._commit_or_rollback()

    def restore_role_permission(self, role_id: int, permission_id: int) -> None:
        """Восстанавливает мягко удалённую связь роль-разрешение."""
        role = self._require_role(role_id, include_deleted=True)
        permission = self._require_permission(permission_id, include_deleted=True)
        if role.deleted_at is not None:
            raise RoleNotFoundError("Нельзя восстановить связь с мягко удалённой ролью.")
        if permission.deleted_at is not None:
            raise PermissionNotFoundError(
                "Нельзя восстановить связь с мягко удалённым разрешением."
            )

        link = self._require_deleted_permission_role_link(role_id, permission_id)
        link.deleted_at = None
        link.deleted_by = None
        self._commit_or_rollback()

    def _require_user(self, user_id: int, *, include_deleted: bool = False) -> User:
        stmt = select(User).where(User.id == user_id)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))

        user = self._db.scalar(stmt)
        if user is None:
            raise RbacUserNotFoundError("Пользователь не найден.")
        return user

    def _require_role(self, role_id: int, *, include_deleted: bool) -> Role:
        stmt = select(Role).where(Role.id == role_id)
        if not include_deleted:
            stmt = stmt.where(Role.deleted_at.is_(None))

        role = self._db.scalar(stmt)
        if role is None:
            raise RoleNotFoundError("Роль не найдена.")
        return role

    def _require_permission(self, permission_id: int, *, include_deleted: bool) -> Permission:
        stmt = select(Permission).where(Permission.id == permission_id)
        if not include_deleted:
            stmt = stmt.where(Permission.deleted_at.is_(None))

        permission = self._db.scalar(stmt)
        if permission is None:
            raise PermissionNotFoundError("Разрешение не найдено.")
        return permission

    def _require_user_role_link(self, user_id: int, role_id: int) -> UserRole:
        link = self._db.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
            )
        )
        if link is None:
            raise UserRoleNotFoundError("Связь пользователь-роль не найдена.")
        return link

    def _require_active_user_role_link(self, user_id: int, role_id: int) -> UserRole:
        link = self._db.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                UserRole.deleted_at.is_(None),
            )
        )
        if link is None:
            raise UserRoleNotFoundError("Активная связь пользователь-роль не найдена.")
        return link

    def _require_deleted_user_role_link(self, user_id: int, role_id: int) -> UserRole:
        link = self._db.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                UserRole.deleted_at.is_not(None),
            )
        )
        if link is None:
            raise UserRoleNotFoundError("Мягко удалённая связь пользователь-роль не найдена.")
        return link

    def _require_permission_role_link(self, role_id: int, permission_id: int) -> PermissionRole:
        link = self._db.scalar(
            select(PermissionRole).where(
                PermissionRole.role_id == role_id,
                PermissionRole.permission_id == permission_id,
            )
        )
        if link is None:
            raise PermissionRoleNotFoundError("Связь роль-разрешение не найдена.")
        return link

    def _require_active_permission_role_link(
        self,
        role_id: int,
        permission_id: int,
    ) -> PermissionRole:
        link = self._db.scalar(
            select(PermissionRole).where(
                PermissionRole.role_id == role_id,
                PermissionRole.permission_id == permission_id,
                PermissionRole.deleted_at.is_(None),
            )
        )
        if link is None:
            raise PermissionRoleNotFoundError("Активная связь роль-разрешение не найдена.")
        return link

    def _require_deleted_permission_role_link(
        self,
        role_id: int,
        permission_id: int,
    ) -> PermissionRole:
        link = self._db.scalar(
            select(PermissionRole).where(
                PermissionRole.role_id == role_id,
                PermissionRole.permission_id == permission_id,
                PermissionRole.deleted_at.is_not(None),
            )
        )
        if link is None:
            raise PermissionRoleNotFoundError("Мягко удалённая связь роль-разрешение не найдена.")
        return link

    def _role_name_exists(self, name: str, exclude_role_id: int | None = None) -> bool:
        stmt = select(Role.id).where(func.lower(Role.name) == name.lower())
        if exclude_role_id is not None:
            stmt = stmt.where(Role.id != exclude_role_id)
        return self._db.scalar(stmt) is not None

    def _role_slug_exists(self, slug: str, exclude_role_id: int | None = None) -> bool:
        stmt = select(Role.id).where(func.lower(Role.slug) == slug.lower())
        if exclude_role_id is not None:
            stmt = stmt.where(Role.id != exclude_role_id)
        return self._db.scalar(stmt) is not None

    def _permission_name_exists(self, name: str, exclude_permission_id: int | None = None) -> bool:
        stmt = select(Permission.id).where(func.lower(Permission.name) == name.lower())
        if exclude_permission_id is not None:
            stmt = stmt.where(Permission.id != exclude_permission_id)
        return self._db.scalar(stmt) is not None

    def _permission_slug_exists(self, slug: str, exclude_permission_id: int | None = None) -> bool:
        stmt = select(Permission.id).where(func.lower(Permission.slug) == slug.lower())
        if exclude_permission_id is not None:
            stmt = stmt.where(Permission.id != exclude_permission_id)
        return self._db.scalar(stmt) is not None

    def _username_exists(self, username: str, exclude_user_id: int | None = None) -> bool:
        stmt = select(User.id).where(func.lower(User.username) == username.lower())
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        return self._db.scalar(stmt) is not None

    def _email_exists(self, email: str, exclude_user_id: int | None = None) -> bool:
        stmt = select(User.id).where(func.lower(User.email) == email.lower())
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        return self._db.scalar(stmt) is not None

    def _commit_or_rollback(self, integrity_error: RbacServiceError | None = None) -> None:
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            if integrity_error is not None:
                raise integrity_error from exc
            raise RbacPersistenceError("Ошибка сохранения RBAC-данных.") from exc
        except SQLAlchemyError as exc:
            self._db.rollback()
            raise RbacPersistenceError("Ошибка сохранения RBAC-данных.") from exc

    def _to_user_dto(self, user: User) -> UserDTO:
        roles = sorted(user.roles, key=lambda item: item.id)
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            birthday=user.birthday,
            roles=[self._to_role_dto(role) for role in roles],
        )

    @staticmethod
    def _to_role_dto(role: Role) -> RoleDTO:
        return RoleDTO(
            id=role.id,
            name=role.name,
            slug=role.slug,
            description=role.description,
            created_at=role.created_at,
            created_by=role.created_by,
            deleted_at=role.deleted_at,
            deleted_by=role.deleted_by,
        )

    @staticmethod
    def _to_permission_dto(permission: Permission) -> PermissionDTO:
        return PermissionDTO(
            id=permission.id,
            name=permission.name,
            slug=permission.slug,
            description=permission.description,
            created_at=permission.created_at,
            created_by=permission.created_by,
            deleted_at=permission.deleted_at,
            deleted_by=permission.deleted_by,
        )

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)
