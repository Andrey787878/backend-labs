from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.dependencies import CurrentUserContext, get_current_user_context, require_permission
from app.dto import ReportGenerateResponseDTO
from app.rbac_permissions import PermissionSlugs
from app.report_queue_service import ReportQueueService


router = APIRouter(prefix="/api/report", tags=["reports"])


def get_report_queue_service(db: Session = Depends(get_db)) -> ReportQueueService:
    """Создаёт сервис очереди отчётов в рамках текущей DB-сессии."""
    return ReportQueueService(db=db)


def _raise_http_for_report_error(error: Exception) -> NoReturn:
    """Преобразует ошибки report-сервиса в HTTPException."""
    if isinstance(error, SQLAlchemyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к очереди отчётов. Повторите попытку позже.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Внутренняя ошибка очереди отчётов.",
    ) from error


@router.post(
    "/generate",
    summary="Поставить аналитический отчёт в очередь",
    description=(
        "Создаёт фоновую задачу генерации аналитического отчёта по logs_requests "
        "из ЛР7 и change_logs из ЛР4. Сам отчёт формируется асинхронным worker-ом."
    ),
    response_model=ReportGenerateResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permission(PermissionSlugs.GENERATE_REPORT))],
    responses={
        status.HTTP_202_ACCEPTED: {"description": "Задача генерации отчёта поставлена в очередь."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Пользователь не авторизован."},
        status.HTTP_403_FORBIDDEN: {"description": "Недостаточно прав для генерации отчёта."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Временная ошибка доступа к БД."},
    },
)
def generate_report(
    context: CurrentUserContext = Depends(get_current_user_context),
    settings: Settings = Depends(get_settings),
    queue_service: ReportQueueService = Depends(get_report_queue_service),
) -> ReportGenerateResponseDTO:
    """Ставит аналитический отчёт в DB-backed очередь."""
    try:
        return queue_service.enqueue_report(
            created_by=context.user_id,
            max_attempts=settings.report_job_max_attempts,
        )
    except Exception as exc:
        _raise_http_for_report_error(exc)
