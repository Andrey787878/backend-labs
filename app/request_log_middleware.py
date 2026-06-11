from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

from starlette.background import BackgroundTask, BackgroundTasks
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Message

from app.db import SessionLocal
from app.models import AuthSession
from app.request_log_sanitizer import RequestLogSanitizer
from app.request_log_service import RequestLogService
from app.token_service import TokenDecodeError, TokenHeaderError, TokenService


logger = logging.getLogger(__name__)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Глобально логирует HTTP request/response записи для ЛР7."""

    def __init__(self, app: Any, body_max_chars: int) -> None:
        super().__init__(app)
        self._body_max_chars = body_max_chars
        self._sanitizer = RequestLogSanitizer()
        self._token_service = TokenService()

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Собирает request, пропускает его дальше, затем сохраняет response-log."""
        called_at = datetime.now(timezone.utc)
        request_payload = await self._build_request_payload(request)
        user_id = await asyncio.to_thread(self._resolve_user_id, request.headers.get("Authorization"))

        try:
            response = await call_next(request)
        except Exception:
            log_kwargs = self._build_log_kwargs(
                request=request,
                request_payload=request_payload,
                user_id=user_id,
                response_status=500,
                response_body={"error": "Unhandled application exception"},
                response_headers=None,
                called_at=called_at,
            )
            await asyncio.to_thread(self._save_log_safely, **log_kwargs)
            raise

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        response_payload = self._parse_body(
            body=response_body,
            content_type=response.headers.get("content-type", ""),
        )
        log_kwargs = self._build_log_kwargs(
            request=request,
            request_payload=request_payload,
            user_id=user_id,
            response_status=response.status_code,
            response_body=self._sanitizer.sanitize(response_payload),
            response_headers=self._sanitizer.sanitize(dict(response.headers)),
            called_at=called_at,
        )

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
            background=self._build_background(response.background, log_kwargs),
        )

    def _build_receive(self, body: bytes) -> Any:
        """Возвращает receive-функцию, чтобы downstream endpoints снова прочитали body."""

        async def receive() -> Message:
            return {"type": "http.request", "body": body, "more_body": False}

        return receive

    async def _build_request_payload(self, request: Request) -> dict[str, Any] | None:
        """Формирует очищенное тело запроса для сохранения в logs_requests."""
        content_type = request.headers.get("content-type", "")
        if self._is_multipart(content_type):
            return self._sanitizer.sanitize(self._multipart_body_payload())

        request_body_bytes = await request.body()
        request._receive = self._build_receive(request_body_bytes)  # noqa: SLF001
        parsed_body = self._parse_body(body=request_body_bytes, content_type=content_type)
        return self._sanitizer.sanitize(parsed_body)

    @staticmethod
    def _is_multipart(content_type: str) -> bool:
        return "multipart/form-data" in content_type.lower()

    @staticmethod
    def _multipart_body_payload() -> dict[str, str]:
        return {"_type": "multipart/form-data", "_body": "multipart body omitted"}

    def _parse_body(self, body: bytes, content_type: str) -> dict[str, Any] | None:
        """Парсит JSON/form/text body в JSON-совместимый словарь."""
        if not body:
            return None

        content_type = content_type.lower()
        if self._is_multipart(content_type):
            return self._multipart_body_payload()

        text = body.decode("utf-8", errors="replace")
        truncated = len(text) > self._body_max_chars
        text_for_storage = text[: self._body_max_chars]

        if "application/json" in content_type:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return {**parsed, "_truncated": truncated} if truncated else parsed
                return {"value": parsed, "_truncated": truncated}
            except json.JSONDecodeError:
                return {"raw": text_for_storage, "_truncated": truncated}

        if "application/x-www-form-urlencoded" in content_type:
            parsed_form = parse_qs(text, keep_blank_values=True)
            normalized_form = {
                key: values[0] if len(values) == 1 else values
                for key, values in parsed_form.items()
            }
            return {**normalized_form, "_truncated": truncated} if truncated else normalized_form

        return {"raw": text_for_storage, "_truncated": truncated}

    def _resolve_user_id(self, authorization: str | None) -> int | None:
        """Пытается определить user_id по Bearer access token без изменения ответа."""
        if authorization is None:
            return None

        scheme, _, token = authorization.strip().partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None

        try:
            header = self._token_service.parse_jwt_header(token.strip())
            self._token_service.validate_jwt_header(header)
            payload = self._token_service.decode_access_token(token.strip())
        except (TokenHeaderError, TokenDecodeError):
            return None

        with SessionLocal() as db:
            session = db.query(AuthSession).filter(AuthSession.access_jti == payload.jti).one_or_none()
            if session is None or session.user_id != payload.sub or session.revoked_at is not None:
                return None
            return session.user_id

    def _build_log_kwargs(
        self,
        *,
        request: Request,
        request_payload: dict[str, Any] | None,
        user_id: int | None,
        response_status: int,
        response_body: dict[str, Any] | None,
        response_headers: dict[str, Any] | None,
        called_at: datetime,
    ) -> dict[str, Any]:
        """Собирает данные лога до фоновой записи, не удерживая request-объект."""
        endpoint = request.scope.get("endpoint")
        controller_path = f"{endpoint.__module__}.{endpoint.__qualname__}" if endpoint else None
        controller_method = endpoint.__name__ if endpoint else None
        return {
            "full_url": str(request.url),
            "method": request.method,
            "controller_path": controller_path,
            "controller_method": controller_method,
            "request_body": request_payload,
            "request_headers": self._sanitizer.sanitize(dict(request.headers)),
            "user_id": user_id,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "response_status": response_status,
            "response_body": response_body,
            "response_headers": response_headers,
            "called_at": called_at,
        }

    def _build_background(
        self,
        existing_background: Any,
        log_kwargs: dict[str, Any],
    ) -> BackgroundTask | BackgroundTasks:
        """Добавляет запись лога в background, чтобы клиент не ждал commit в БД."""
        log_task = BackgroundTask(self._save_log_safely, **log_kwargs)
        if existing_background is None:
            return log_task

        background = BackgroundTasks()
        background.add_task(existing_background)
        background.add_task(log_task)
        return background

    def _save_log_safely(
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
    ) -> None:
        """Сохраняет лог и не даёт ошибке логирования сломать пользовательский запрос."""
        try:
            with SessionLocal() as db:
                RequestLogService(db).create_log(
                    full_url=full_url,
                    method=method,
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
        except Exception as exc:  # pragma: no cover - логирование не должно ломать API
            logger.warning("Failed to save request log: %s", exc)
