from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

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
        request_body_bytes = await request.body()
        request._receive = self._build_receive(request_body_bytes)  # noqa: SLF001

        request_payload = self._build_request_payload(request, request_body_bytes)
        user_id = self._resolve_user_id(request)

        try:
            response = await call_next(request)
        except Exception:
            self._save_log_safely(
                request=request,
                request_payload=request_payload,
                user_id=user_id,
                response_status=500,
                response_body={"error": "Unhandled application exception"},
                response_headers=None,
                called_at=called_at,
            )
            raise

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        response_payload = self._parse_body(
            body=response_body,
            content_type=response.headers.get("content-type", ""),
        )

        self._save_log_safely(
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
            background=response.background,
        )

    def _build_receive(self, body: bytes) -> Any:
        """Возвращает receive-функцию, чтобы downstream endpoints снова прочитали body."""

        async def receive() -> Message:
            return {"type": "http.request", "body": body, "more_body": False}

        return receive

    def _build_request_payload(
        self,
        request: Request,
        body: bytes,
    ) -> dict[str, Any] | None:
        """Формирует очищенное тело запроса для сохранения в logs_requests."""
        parsed_body = self._parse_body(body=body, content_type=request.headers.get("content-type", ""))
        return self._sanitizer.sanitize(parsed_body)

    def _parse_body(self, body: bytes, content_type: str) -> dict[str, Any] | None:
        """Парсит JSON/form/text body в JSON-совместимый словарь."""
        if not body:
            return None

        content_type = content_type.lower()
        if "multipart/form-data" in content_type:
            return {"_type": "multipart/form-data", "_body": "multipart body omitted"}

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

    def _resolve_user_id(self, request: Request) -> int | None:
        """Пытается определить user_id по Bearer access token без изменения ответа."""
        authorization = request.headers.get("Authorization")
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

    def _save_log_safely(
        self,
        *,
        request: Request,
        request_payload: dict[str, Any] | None,
        user_id: int | None,
        response_status: int,
        response_body: dict[str, Any] | None,
        response_headers: dict[str, Any] | None,
        called_at: datetime,
    ) -> None:
        """Сохраняет лог и не даёт ошибке логирования сломать пользовательский запрос."""
        try:
            endpoint = request.scope.get("endpoint")
            controller_path = f"{endpoint.__module__}.{endpoint.__qualname__}" if endpoint else None
            controller_method = endpoint.__name__ if endpoint else None
            with SessionLocal() as db:
                RequestLogService(db).create_log(
                    full_url=str(request.url),
                    method=request.method,
                    controller_path=controller_path,
                    controller_method=controller_method,
                    request_body=request_payload,
                    request_headers=self._sanitizer.sanitize(dict(request.headers)),
                    user_id=user_id,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    response_status=response_status,
                    response_body=response_body,
                    response_headers=response_headers,
                    called_at=called_at,
                )
        except Exception as exc:  # pragma: no cover - логирование не должно ломать API
            logger.warning("Failed to save request log: %s", exc)
