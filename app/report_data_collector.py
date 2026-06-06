from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.dto import ReportContentDTO, ReportPeriodDTO, ReportRatingItemDTO, ReportUserRatingItemDTO
from app.models import AuthSession, ChangeLog, LogRequest, Permission, PermissionRole, Role, UserRole


class ReportDataCollector:
    """Собирает агрегаты для аналитического отчёта ЛР8."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def collect(self, *, interval_hours: int) -> ReportContentDTO:
        """Собирает report content за последние interval_hours часов."""
        to_dt = datetime.now(timezone.utc)
        from_dt = to_dt - timedelta(hours=interval_hours)
        return ReportContentDTO(
            type="Analytics report",
            generated_at=to_dt,
            period=ReportPeriodDTO(from_at=from_dt, to=to_dt, hours=interval_hours),
            method_rating=self._collect_method_rating(from_dt),
            entity_rating=self._collect_entity_rating(from_dt),
            user_rating=self._collect_user_rating(from_dt),
        )

    def _collect_method_rating(self, from_dt: datetime) -> list[ReportRatingItemDTO]:
        """Собирает рейтинг вызываемых методов из logs_requests."""
        method_name = func.coalesce(LogRequest.controller_path, LogRequest.full_url)
        rows = self._db.execute(
            select(
                method_name.label("name"),
                func.count(LogRequest.id).label("total"),
                func.max(LogRequest.called_at).label("last_operation_at"),
            )
            .where(LogRequest.called_at >= from_dt)
            .group_by(method_name)
            .order_by(func.count(LogRequest.id).desc(), func.max(LogRequest.called_at).desc())
        ).all()
        return [
            ReportRatingItemDTO(
                name=str(row.name),
                count=int(row.total),
                last_operation_at=row.last_operation_at,
            )
            for row in rows
        ]

    def _collect_entity_rating(self, from_dt: datetime) -> list[ReportRatingItemDTO]:
        """Собирает рейтинг изменяемых сущностей из change_logs."""
        rows = self._db.execute(
            select(
                ChangeLog.entity_type.label("name"),
                func.count(ChangeLog.id).label("total"),
                func.max(ChangeLog.created_at).label("last_operation_at"),
            )
            .where(ChangeLog.created_at >= from_dt)
            .group_by(ChangeLog.entity_type)
            .order_by(func.count(ChangeLog.id).desc(), func.max(ChangeLog.created_at).desc())
        ).all()
        return [
            ReportRatingItemDTO(
                name=str(row.name),
                count=int(row.total),
                last_operation_at=row.last_operation_at,
            )
            for row in rows
        ]

    def _collect_user_rating(self, from_dt: datetime) -> list[ReportUserRatingItemDTO]:
        """Собирает пользовательский рейтинг по запросам, изменениям, авторизациям и правам."""
        request_stats = self._collect_request_stats(from_dt)
        change_stats = self._collect_change_stats(from_dt)
        auth_stats = self._collect_auth_stats(from_dt)
        permission_stats = self._collect_permission_stats()
        user_ids = set(request_stats) | set(change_stats) | set(auth_stats) | set(permission_stats)

        items: list[ReportUserRatingItemDTO] = []
        for user_id in sorted(user_ids):
            request_count, request_last = request_stats.get(user_id, (0, None))
            change_count, change_last = change_stats.get(user_id, (0, None))
            auth_count, auth_last = auth_stats.get(user_id, (0, None))
            last_values = [value for value in (request_last, change_last, auth_last) if value is not None]
            items.append(
                ReportUserRatingItemDTO(
                    user_id=user_id,
                    request_count=request_count,
                    change_count=change_count,
                    auth_count=auth_count,
                    permission_count=permission_stats.get(user_id, 0),
                    last_operation_at=max(last_values) if last_values else None,
                )
            )

        return sorted(
            items,
            key=lambda item: (
                item.request_count + item.change_count + item.auth_count,
                item.last_operation_at or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )

    def _collect_request_stats(self, from_dt: datetime) -> dict[int, tuple[int, datetime | None]]:
        rows = self._db.execute(
            select(
                LogRequest.user_id,
                func.count(LogRequest.id),
                func.max(LogRequest.called_at),
            )
            .where(LogRequest.called_at >= from_dt, LogRequest.user_id.is_not(None))
            .group_by(LogRequest.user_id)
        ).all()
        return {int(row[0]): (int(row[1]), row[2]) for row in rows}

    def _collect_change_stats(self, from_dt: datetime) -> dict[int, tuple[int, datetime | None]]:
        rows = self._db.execute(
            select(
                ChangeLog.created_by,
                func.count(ChangeLog.id),
                func.max(ChangeLog.created_at),
            )
            .where(ChangeLog.created_at >= from_dt)
            .group_by(ChangeLog.created_by)
        ).all()
        return {int(row[0]): (int(row[1]), row[2]) for row in rows}

    def _collect_auth_stats(self, from_dt: datetime) -> dict[int, tuple[int, datetime | None]]:
        rows = self._db.execute(
            select(
                AuthSession.user_id,
                func.count(AuthSession.id),
                func.max(AuthSession.created_at),
            )
            .where(AuthSession.created_at >= from_dt)
            .group_by(AuthSession.user_id)
        ).all()
        return {int(row[0]): (int(row[1]), row[2]) for row in rows}

    def _collect_permission_stats(self) -> dict[int, int]:
        rows = self._db.execute(
            select(UserRole.user_id, func.count(distinct(Permission.id)))
            .join(Role, Role.id == UserRole.role_id)
            .join(PermissionRole, PermissionRole.role_id == Role.id)
            .join(Permission, Permission.id == PermissionRole.permission_id)
            .where(
                UserRole.deleted_at.is_(None),
                Role.deleted_at.is_(None),
                PermissionRole.deleted_at.is_(None),
                Permission.deleted_at.is_(None),
            )
            .group_by(UserRole.user_id)
        ).all()
        return {int(row[0]): int(row[1]) for row in rows}
