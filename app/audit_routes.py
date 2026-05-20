from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn, TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit_service import (
    AUDIT_ENTITY_PERMISSION,
    AUDIT_ENTITY_ROLE,
    AUDIT_ENTITY_USER,
    AuditConflictError,
    AuditNotFoundError,
    AuditPersistenceError,
    AuditService,
    AuditServiceError,
)
from app.dependencies import (
    CurrentUserContext,
    PermissionDeniedError,
    get_audit_service,
    get_current_user_context,
    get_db,
    require_permission,
    user_has_permission,
)
from app.dto import ChangeLogCollectionDTO, ChangeLogDTO
from app.rbac_permissions import PermissionSlugs


router = APIRouter(prefix="/api/ref", tags=["audit"])
_ResultT = TypeVar("_ResultT")


def _raise_http_for_audit_error(
    error: AuditServiceError | SQLAlchemyError | ValueError,
) -> NoReturn:
    """Преобразует доменные audit-ошибки в HTTPException."""
    if isinstance(error, AuditNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, AuditConflictError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    if isinstance(error, AuditPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка сохранения данных. Повторите попытку позже.",
        )
    if isinstance(error, SQLAlchemyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к данным. Повторите попытку позже.",
        )
    if isinstance(error, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    if isinstance(error, AuditServiceError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Внутренняя ошибка audit-сервиса.",
    ) from error


def _call_audit(fn: Callable[[], _ResultT]) -> _ResultT:
    """Выполняет audit-операцию и маппит доменные ошибки в HTTPException."""
    try:
        return fn()
    except (AuditServiceError, SQLAlchemyError, ValueError) as exc:
        _raise_http_for_audit_error(exc)


@router.get(
    "/user/{user_id}/story",
    summary="История изменений пользователя",
    response_model=ChangeLogCollectionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.GET_STORY_USER))],
)
def user_story(
    user_id: int,
    audit_service: AuditService = Depends(get_audit_service),
) -> ChangeLogCollectionDTO:
    """Возвращает историю изменений пользователя."""
    return _call_audit(lambda: audit_service.list_user_story(user_id=user_id))


@router.get(
    "/policy/role/{role_id}/story",
    summary="История изменений роли",
    response_model=ChangeLogCollectionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.GET_STORY_ROLE))],
)
def role_story(
    role_id: int,
    audit_service: AuditService = Depends(get_audit_service),
) -> ChangeLogCollectionDTO:
    """Возвращает историю изменений роли."""
    return _call_audit(lambda: audit_service.list_role_story(role_id=role_id))


@router.get(
    "/policy/permission/{permission_id}/story",
    summary="История изменений разрешения",
    response_model=ChangeLogCollectionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.GET_STORY_PERMISSION))],
)
def permission_story(
    permission_id: int,
    audit_service: AuditService = Depends(get_audit_service),
) -> ChangeLogCollectionDTO:
    """Возвращает историю изменений разрешения."""
    return _call_audit(lambda: audit_service.list_permission_story(permission_id=permission_id))


@router.post(
    "/changelog/{log_id}/restore",
    summary="Откат сущности к состоянию before из change log",
    response_model=ChangeLogDTO,
    status_code=status.HTTP_200_OK,
)
def restore_from_log(
    log_id: int,
    context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
) -> ChangeLogDTO:
    """Восстанавливает состояние сущности по записи change log."""
    log = _call_audit(lambda: audit_service.get_log(log_id=log_id))
    required_permission = _call_audit(lambda: _resolve_restore_permission(log.entity_type))

    try:
        has_permission = user_has_permission(
            db=db,
            user_id=context.user_id,
            permission_slug=required_permission,
        )
    except SQLAlchemyError as exc:
        _raise_http_for_audit_error(exc)

    if not has_permission:
        raise PermissionDeniedError(required_permission)

    return _call_audit(lambda: audit_service.restore_from_log(log_id=log_id, actor_user_id=context.user_id))


def _resolve_restore_permission(entity_type: str) -> str:
    """Определяет permission-slug, требуемый для restore-from-log."""
    if entity_type == AUDIT_ENTITY_USER:
        return PermissionSlugs.RESTORE_USER
    if entity_type == AUDIT_ENTITY_ROLE:
        return PermissionSlugs.RESTORE_ROLE
    if entity_type == AUDIT_ENTITY_PERMISSION:
        return PermissionSlugs.RESTORE_PERMISSION

    raise AuditConflictError("Неподдерживаемый entity_type в change log.")
