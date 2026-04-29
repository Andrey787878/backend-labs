from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import models
from app.auth_routes import router as auth_router
from app.config import get_settings
from app.dependencies import PermissionDeniedError
from app.rbac_routes import router as rbac_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Lifecycle hooks приложения. Схема БД управляется Alembic-миграциями."""
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.add_exception_handler(PermissionDeniedError, _permission_denied_handler)
    app.include_router(auth_router)
    app.include_router(rbac_router)

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
