from __future__ import annotations

import json
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dto import LogRequestCollectionDTO, LogRequestDTO
from app.dependencies import require_permission
from app.rbac_permissions import PermissionSlugs
from app.request_log_service import RequestLogNotFoundError, RequestLogService
from app.schemas import LogRequestFilterItem, LogRequestIndexQuery, LogRequestSortItem


router = APIRouter(prefix="/api/ref/log", tags=["request-logs"])


def get_request_log_service(db: Session = Depends(get_db)) -> RequestLogService:
    """Создаёт сервис request/response логов в рамках текущей DB-сессии."""
    return RequestLogService(db=db)


def parse_log_request_index_query(
    filter_: str | None = Query(
        default=None,
        alias="filter",
        description=(
            "JSON-массив фильтров. Пример: "
            '[{"key":"response_status","value":"200"}]'
        ),
    ),
    sort_by: str | None = Query(
        default=None,
        alias="sortBy",
        description=(
            "JSON-массив сортировок. Пример: "
            '[{"key":"called_at","order":"desc"}]'
        ),
    ),
    page: int = Query(default=1, ge=1, description="Номер страницы."),
    count: int = Query(default=10, ge=1, le=100, description="Количество элементов на странице."),
) -> LogRequestIndexQuery:
    """Валидирует query-параметры списка request/response логов."""
    try:
        filters = _parse_items(filter_, LogRequestFilterItem, "filter")
        sort_items = _parse_items(sort_by, LogRequestSortItem, "sortBy")
        return LogRequestIndexQuery(filters=filters, sort_by=sort_items, page=page, count=count)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _parse_items(raw_value: str | None, model: type[Any], parameter_name: str) -> list[Any]:
    """Парсит JSON-массив query-параметра в список Pydantic-моделей."""
    if raw_value is None or not raw_value.strip():
        return []

    parsed = json.loads(raw_value)
    if not isinstance(parsed, list):
        raise ValueError(f"{parameter_name} должен быть JSON-массивом.")
    return [model.model_validate(item) for item in parsed]


def _raise_http_for_request_log_error(error: Exception) -> NoReturn:
    """Преобразует ошибки request-log сервиса в HTTPException."""
    if isinstance(error, RequestLogNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    if isinstance(error, SQLAlchemyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к логам. Повторите попытку позже.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Внутренняя ошибка request-log сервиса.",
    ) from error


@router.get(
    "/request",
    summary="Список request/response логов",
    description=(
        "Возвращает список HTTP request/response логов с фильтрацией, сортировкой "
        "и пагинацией. Доступно только администраторам с permission get-list-log."
    ),
    response_model=LogRequestCollectionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.GET_LIST_LOG))],
    responses={
        status.HTTP_200_OK: {"description": "Список логов успешно получен."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Пользователь не авторизован."},
        status.HTTP_403_FORBIDDEN: {"description": "Недостаточно прав для просмотра списка логов."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Некорректные filter/sortBy/page/count."},
    },
)
def list_request_logs(
    query: LogRequestIndexQuery = Depends(parse_log_request_index_query),
    service: RequestLogService = Depends(get_request_log_service),
) -> LogRequestCollectionDTO:
    """Возвращает страницу request/response логов."""
    try:
        return service.list_logs(query=query)
    except Exception as exc:
        _raise_http_for_request_log_error(exc)


@router.get(
    "/request/{log_request_id}",
    summary="Получить request/response лог по ID",
    description="Возвращает полную запись request/response лога. Доступно с permission read-log.",
    response_model=LogRequestDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.READ_LOG))],
    responses={
        status.HTTP_200_OK: {"description": "Лог успешно получен."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Пользователь не авторизован."},
        status.HTTP_403_FORBIDDEN: {"description": "Недостаточно прав для просмотра лога."},
        status.HTTP_404_NOT_FOUND: {"description": "Лог не найден."},
    },
)
def get_request_log(
    log_request_id: int,
    service: RequestLogService = Depends(get_request_log_service),
) -> LogRequestDTO:
    """Возвращает полную запись request/response лога."""
    try:
        return service.get_log(log_request_id=log_request_id)
    except Exception as exc:
        _raise_http_for_request_log_error(exc)


@router.delete(
    "/request/{log_request_id}",
    summary="Удалить request/response лог",
    description="Физически удаляет request/response лог. Доступно с permission delete-log.",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_LOG))],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Лог успешно удалён."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Пользователь не авторизован."},
        status.HTTP_403_FORBIDDEN: {"description": "Недостаточно прав для удаления лога."},
        status.HTTP_404_NOT_FOUND: {"description": "Лог не найден."},
    },
)
def delete_request_log(
    log_request_id: int,
    service: RequestLogService = Depends(get_request_log_service),
) -> Response:
    """Физически удаляет request/response лог и возвращает 204."""
    try:
        service.delete_log(log_request_id=log_request_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _raise_http_for_request_log_error(exc)
