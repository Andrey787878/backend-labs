import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import models
from app.audit_events import register_audit_event_listeners
from app.audit_routes import router as audit_router
from app.auth_routes import router as auth_router
from app.config import get_settings
from app.dependencies import PermissionDeniedError
from app.git_webhook_routes import router as git_webhook_router
from app.rbac_routes import router as rbac_router
from app.report_routes import router as report_router
from app.report_worker import run_report_worker, stop_report_worker
from app.request_log_middleware import RequestLogMiddleware
from app.request_log_routes import router as request_log_router
from app.request_log_scheduler import (
    run_request_log_cleanup_scheduler,
    stop_request_log_cleanup_scheduler,
)

APPLICATION_LOGGER_NAMES = (
    "app.report_job_processor",
    "app.report_sender",
    "app.report_worker",
    "app.request_log_middleware",
    "app.request_log_scheduler",
)


def configure_application_logging() -> None:
    """Включает INFO-логи фоновых сервисов, чтобы их было видно при сдаче."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    for logger_name in APPLICATION_LOGGER_NAMES:
        logging.getLogger(logger_name).setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hooks приложения. Схема БД управляется Alembic-миграциями."""
    settings = get_settings()
    cleanup_task = asyncio.create_task(
        run_request_log_cleanup_scheduler(
            retention_hours=settings.request_log_retention_hours,
            interval_seconds=settings.request_log_clean_interval_seconds,
        )
    )
    report_worker_task = asyncio.create_task(run_report_worker(settings))
    app.state.request_log_cleanup_task = cleanup_task
    app.state.report_worker_task = report_worker_task
    try:
        yield
    finally:
        await stop_report_worker(report_worker_task)
        await stop_request_log_cleanup_scheduler(cleanup_task)


def create_app() -> FastAPI:
    configure_application_logging()
    settings = get_settings()
    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    register_audit_event_listeners()
    app.add_middleware(
        RequestLogMiddleware,
        body_max_chars=settings.request_log_body_max_chars,
    )
    app.add_exception_handler(PermissionDeniedError, _permission_denied_handler)
    app.include_router(auth_router)
    app.include_router(rbac_router)
    app.include_router(audit_router)
    app.include_router(git_webhook_router)
    app.include_router(request_log_router)
    app.include_router(report_router)

    return app


async def _permission_denied_handler(
    _: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    """Единый формат ответа 403 при отсутствии RBAC-permission."""
    return JSONResponse(
        status_code=403,
        content={"error": f"Access denied. Required permission: {exc.permission_slug}"},
    )


app = create_app()
