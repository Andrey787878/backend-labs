from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from app.dto import LogRequestCollectionDTO, LogRequestDTO, LogRequestListItemDTO
from app.models import LogRequest
from app.request_log_sanitizer import RequestLogSanitizer
from app.schemas import LogRequestIndexQuery


class RequestLogNotFoundError(Exception):
    """Request/response лог не найден."""


class RequestLogService:
    """Сервис просмотра, записи и удаления request/response логов."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._sanitizer = RequestLogSanitizer()

    def create_log(
        self,
        *,
        full_url: str,
        method: str,
        controller_path: str | None,
        controller_method: str | None,
        request_body: dict[str, Any] | None,
        request_headers: dict[str, Any] | None,
        user_id: int | None,
        ip_address: str | None,
        user_agent: str | None,
        response_status: int,
        response_body: dict[str, Any] | None,
        response_headers: dict[str, Any] | None,
        called_at: datetime,
    ) -> LogRequestDTO:
        """Сохраняет одну запись request/response лога."""
        log = LogRequest(
            full_url=full_url,
            method=method.upper(),
            controller_path=controller_path,
            controller_method=controller_method,
            request_body=request_body,
            request_headers=request_headers,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            response_status=response_status,
            response_body=response_body,
            response_headers=response_headers,
            called_at=called_at,
        )
        self._db.add(log)
        self._db.commit()
        self._db.refresh(log)
        return self._to_dto(log)

    def list_logs(self, query: LogRequestIndexQuery) -> LogRequestCollectionDTO:
        """Возвращает список логов с фильтрацией, сортировкой и пагинацией."""
        stmt = self._apply_filters(select(LogRequest), query)
        total = self._db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = self._apply_sorting(stmt, query)
        offset = (query.page - 1) * query.count
        rows = self._db.scalars(stmt.offset(offset).limit(query.count)).all()
        pages = ceil(total / query.count) if total else 0

        return LogRequestCollectionDTO(
            items=[self._to_list_item_dto(row) for row in rows],
            page=query.page,
            pages=pages,
            total=total,
            count=query.count,
        )

    def get_log(self, log_request_id: int) -> LogRequestDTO:
        """Возвращает полную запись request/response лога по id."""
        log = self._db.get(LogRequest, log_request_id)
        if log is None:
            raise RequestLogNotFoundError(f"Request log #{log_request_id} не найден.")
        return self._to_dto(log)

    def delete_log(self, log_request_id: int) -> None:
        """Физически удаляет одну запись request/response лога."""
        log = self._db.get(LogRequest, log_request_id)
        if log is None:
            raise RequestLogNotFoundError(f"Request log #{log_request_id} не найден.")
        self._db.delete(log)
        self._db.commit()

    def delete_older_than(self, retention_hours: int) -> int:
        """Удаляет логи старше указанного количества часов и возвращает их число."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
        result = self._db.execute(delete(LogRequest).where(LogRequest.called_at < threshold))
        self._db.commit()
        return int(result.rowcount or 0)

    def _apply_filters(
        self,
        stmt: Select[tuple[LogRequest]],
        query: LogRequestIndexQuery,
    ) -> Select[tuple[LogRequest]]:
        """Применяет только разрешённые фильтры из query-схемы."""
        for item in query.filters:
            column = getattr(LogRequest, item.key)
            if item.key == "user_agent":
                stmt = stmt.where(column.ilike(f"%{item.value}%"))
            elif item.key in {"user_id", "response_status"}:
                stmt = stmt.where(column == int(item.value))
            else:
                stmt = stmt.where(column == item.value)
        return stmt

    def _apply_sorting(
        self,
        stmt: Select[tuple[LogRequest]],
        query: LogRequestIndexQuery,
    ) -> Select[tuple[LogRequest]]:
        """Применяет сортировку из белого списка или дефолтную called_at desc."""
        sort_items = query.sort_by or []
        if not sort_items:
            return stmt.order_by(LogRequest.called_at.desc(), LogRequest.id.desc())

        for item in sort_items:
            column = getattr(LogRequest, item.key)
            stmt = stmt.order_by(column.asc() if item.order == "asc" else column.desc())
        return stmt

    def _to_dto(self, log: LogRequest) -> LogRequestDTO:
        """Преобразует ORM-модель в полную DTO."""
        return LogRequestDTO(
            id=log.id,
            full_url=self._sanitize_frontend(log.full_url),
            method=self._sanitize_frontend(log.method),
            controller_path=self._sanitize_frontend(log.controller_path),
            controller_method=self._sanitize_frontend(log.controller_method),
            request_body=self._sanitize_frontend(log.request_body),
            request_headers=self._sanitize_frontend(log.request_headers),
            user_id=log.user_id,
            ip_address=self._sanitize_frontend(log.ip_address),
            user_agent=self._sanitize_frontend(log.user_agent),
            response_status=log.response_status,
            response_body=self._sanitize_frontend(log.response_body),
            response_headers=self._sanitize_frontend(log.response_headers),
            called_at=log.called_at,
            created_at=log.created_at,
        )

    def _to_list_item_dto(self, log: LogRequest) -> LogRequestListItemDTO:
        """Преобразует ORM-модель в короткую DTO для списка."""
        return LogRequestListItemDTO(
            id=log.id,
            full_url=self._sanitize_frontend(log.full_url),
            method=self._sanitize_frontend(log.method),
            controller_path=self._sanitize_frontend(log.controller_path),
            controller_method=self._sanitize_frontend(log.controller_method),
            response_status=log.response_status,
            called_at=log.called_at,
        )

    def _sanitize_frontend(self, value: Any) -> Any:
        """Готовит значение лога к безопасной отдаче во фронт."""
        return self._sanitizer.sanitize_for_frontend(value)
