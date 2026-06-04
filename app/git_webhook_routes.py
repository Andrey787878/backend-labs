from __future__ import annotations

from hmac import compare_digest
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.deployment_lock import DeploymentLockError
from app.deployment_service import (
    DeploymentCommandError,
    DeploymentRepositoryError,
    DeploymentService,
    DeploymentServiceError,
)
from app.dto import DeploymentResponseDTO
from app.schemas import GitWebhookRequest


router = APIRouter(prefix="/hooks", tags=["git-webhook"])

GIT_WEBHOOK_REQUEST_SCHEMA = {
    "type": "object",
    "required": ["secret_key"],
    "additionalProperties": False,
    "properties": {
        "secret_key": {
            "type": "string",
            "description": "Секретный ключ webhook-а из GIT_WEBHOOK_SECRET.",
            "example": "00000000-0000-0000-0000-000000000000",
        }
    },
}


@router.post(
    "/git",
    summary="Запустить обновление проекта через Git webhook",
    description=(
        "Открытый webhook ЛР6 без JWT/RBAC. Принимает secret_key в JSON или теле формы, "
        "сравнивает его с GIT_WEBHOOK_SECRET, ставит блокировку deployment-процесса и "
        "выполняет Git-команды checkout, reset --hard, pull в корне проекта."
    ),
    response_model=DeploymentResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Проект успешно обновлён через Git."},
        status.HTTP_403_FORBIDDEN: {"description": "Неверный secret_key."},
        status.HTTP_409_CONFLICT: {"description": "Обновление уже выполняется другим процессом."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Некорректный body или secret_key."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Ошибка Git-репозитория или выполнения Git-команд."
        },
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": GIT_WEBHOOK_REQUEST_SCHEMA,
                    "example": {"secret_key": "00000000-0000-0000-0000-000000000000"},
                },
                "application/x-www-form-urlencoded": {
                    "schema": GIT_WEBHOOK_REQUEST_SCHEMA,
                },
                "multipart/form-data": {
                    "schema": GIT_WEBHOOK_REQUEST_SCHEMA,
                },
            },
        }
    },
)
async def update_from_git(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> DeploymentResponseDTO:
    """Проверяет secret_key и синхронно выполняет Git deployment."""
    payload = await _extract_payload(request)
    if not compare_digest(payload.secret_key, settings.git_webhook_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret key")

    service = DeploymentService(
        project_root=Path.cwd(),
        branch=settings.git_default_branch,
        lock_ttl_seconds=settings.git_webhook_lock_ttl_seconds,
        command_timeout_seconds=settings.git_webhook_command_timeout_seconds,
    )

    try:
        client_ip = request.client.host if request.client else None
        return service.deploy(client_ip=client_ip)
    except DeploymentLockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deployment already in progress",
        ) from exc
    except DeploymentCommandError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Deployment failed",
                "command": exc.result.command,
                "return_code": exc.result.return_code,
                "stderr": exc.result.stderr,
            },
        ) from exc
    except (DeploymentRepositoryError, DeploymentServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def _extract_payload(request: Request) -> GitWebhookRequest:
    """Извлекает secret_key из JSON или form-urlencoded/form-data body."""
    content_type = request.headers.get("content-type", "").lower()

    try:
        if "application/json" in content_type:
            raw_payload = await request.json()
        elif "form" in content_type:
            form = await request.form()
            raw_payload = dict(form)
        else:
            raw_payload = await request.json()

        return GitWebhookRequest.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="secret_key is required",
        ) from exc
