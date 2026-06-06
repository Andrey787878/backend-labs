from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, JSON, Date, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, and_, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# ==================== ЛР2: Авторизация ====================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    birthday: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("uq_users_username_ci", func.lower(username), unique=True),
        Index("uq_users_email_ci", func.lower(email), unique=True),
    )

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    change_logs: Mapped[list[ChangeLog]] = relationship(
        back_populates="user",
        foreign_keys="ChangeLog.created_by",
    )
    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )
    roles: Mapped[list[Role]] = relationship(
        secondary="role_user",
        primaryjoin=lambda: and_(
            User.id == UserRole.user_id,
            UserRole.deleted_at.is_(None),
        ),
        secondaryjoin=lambda: and_(
            Role.id == UserRole.role_id,
            Role.deleted_at.is_(None),
        ),
        viewonly=True,
        overlaps="user_roles,users,role,user",
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    access_jti: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    refresh_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


# ==================== ЛР3: RBAC ====================
class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.role_id",
    )
    permission_roles: Mapped[list[PermissionRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        foreign_keys="PermissionRole.role_id",
    )
    users: Mapped[list[User]] = relationship(
        secondary="role_user",
        primaryjoin=lambda: and_(
            Role.id == UserRole.role_id,
            UserRole.deleted_at.is_(None),
        ),
        secondaryjoin=lambda: User.id == UserRole.user_id,
        viewonly=True,
        overlaps="user_roles,user,role,roles",
    )
    permissions: Mapped[list[Permission]] = relationship(
        secondary="permission_role",
        primaryjoin=lambda: and_(
            Role.id == PermissionRole.role_id,
            PermissionRole.deleted_at.is_(None),
        ),
        secondaryjoin=lambda: and_(
            Permission.id == PermissionRole.permission_id,
            Permission.deleted_at.is_(None),
        ),
        viewonly=True,
        overlaps="permission_roles,permission,roles,permissions",
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    permission_roles: Mapped[list[PermissionRole]] = relationship(
        back_populates="permission",
        cascade="all, delete-orphan",
        foreign_keys="PermissionRole.permission_id",
    )
    roles: Mapped[list[Role]] = relationship(
        secondary="permission_role",
        primaryjoin=lambda: and_(
            Permission.id == PermissionRole.permission_id,
            PermissionRole.deleted_at.is_(None),
        ),
        secondaryjoin=lambda: and_(
            Role.id == PermissionRole.role_id,
            Role.deleted_at.is_(None),
        ),
        viewonly=True,
        overlaps="permission_roles,permission,role,permissions",
    )


class UserRole(Base):
    __tablename__ = "role_user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("uq_role_user_user_id_role_id", "user_id", "role_id", unique=True),
    )

    user: Mapped[User] = relationship(
        back_populates="user_roles",
        foreign_keys=[user_id],
        overlaps="roles,users",
    )
    role: Mapped[Role] = relationship(
        back_populates="user_roles",
        foreign_keys=[role_id],
        overlaps="roles,users",
    )


class PermissionRole(Base):
    __tablename__ = "permission_role"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("uq_permission_role_role_id_permission_id", "role_id", "permission_id", unique=True),
    )

    role: Mapped[Role] = relationship(
        back_populates="permission_roles",
        foreign_keys=[role_id],
        overlaps="roles,permissions",
    )
    permission: Mapped[Permission] = relationship(
        back_populates="permission_roles",
        foreign_keys=[permission_id],
        overlaps="roles,permissions",
    )


# ==================== ЛР4: Аудит-лог ====================
class ChangeLog(Base):
    __tablename__ = "change_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    before: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    after: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    user: Mapped[User] = relationship(
        back_populates="change_logs",
        foreign_keys=[created_by],
    )


# ==================== ЛР7: Request/Response Logging ====================
class LogRequest(Base):
    __tablename__ = "logs_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    controller_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    controller_method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_body: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    request_headers: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_headers: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_logs_requests_controller_path", "controller_path"),
    )


# ==================== ЛР8: Queued Analytics Reports ====================
class ReportJob(Base):
    __tablename__ = "report_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    run_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )
