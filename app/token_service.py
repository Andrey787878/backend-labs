from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.config import Settings, get_settings


class TokenServiceError(Exception):
    """Базовое исключение ошибок работы с токенами."""


class TokenHeaderError(TokenServiceError):
    """Ошибка чтения или валидации JWT header."""


class TokenDecodeError(TokenServiceError):
    """Ошибка декодирования и проверки access token."""


@dataclass(frozen=True)
class AccessTokenPayload:
    sub: int
    jti: str
    iat: datetime
    exp: datetime
    token_type: Literal["access"]


class TokenService:
    """Создает и проверяет токены"""
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def create_access_token(self, user_id: int, jti: str) -> str:
        if user_id <= 0:
            raise ValueError("user_id должен быть положительным целым числом.")
        if not jti.strip():
            raise ValueError("jti не должен быть пустым.")

        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(minutes=self._settings.access_token_ttl_minutes)

        payload = {
            "sub": str(user_id),
            "jti": jti,
            "iat": issued_at,
            "exp": expires_at,
            "type": "access",
        }

        algorithm = self._settings.jwt_algorithm
        return jwt.encode(payload, self._settings.jwt_secret, algorithm=algorithm)

    def parse_jwt_header(self, token: str) -> dict[str, str]:
        """Извлекает header JWT."""
        if not token.strip():
            raise TokenHeaderError("Токен не должен быть пустым.")

        try:
            raw_header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise TokenHeaderError("Не удалось распарсить header JWT.") from exc

        parsed_header: dict[str, str] = {}
        for key, value in raw_header.items():
            if value is None:
                parsed_header[str(key)] = ""
            elif isinstance(value, str):
                parsed_header[str(key)] = value
            else:
                parsed_header[str(key)] = str(value)

        return parsed_header

    def validate_jwt_header(self, header: dict[str, str]) -> None:
        """Проверяет безопасность header JWT."""
        alg = header.get("alg")
        if not alg or not alg.strip():
            raise TokenHeaderError("В header JWT отсутствует поле alg.")

        if alg != self._settings.jwt_algorithm:
            raise TokenHeaderError("Алгоритм из header JWT не соответствует настройке сервера.")

        typ = header.get("typ")
        if typ is not None and not typ.strip():
            raise TokenHeaderError("Поле typ в header JWT не должно быть пустым.")

    def _to_utc_datetime(self, value: Any, field_name: str) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)

        raise TokenDecodeError(f"Поле {field_name} должно содержать корректное время.")

    def decode_access_token(self, token: str) -> AccessTokenPayload:
        header = self.parse_jwt_header(token)
        self.validate_jwt_header(header)

        try:
            decoded_payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
                options={"require": ["sub", "jti", "iat", "exp", "type"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenDecodeError("Срок действия access token истек.") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenDecodeError("Access token невалиден.") from exc

        token_type = decoded_payload.get("type")
        if token_type != "access":
            raise TokenDecodeError('Поле type должно быть равно "access".')

        sub_raw = decoded_payload.get("sub")
        try:
            sub = int(sub_raw)
        except (TypeError, ValueError) as exc:
            raise TokenDecodeError("Поле sub должно содержать id пользователя.") from exc

        jti_raw = decoded_payload.get("jti")
        if not isinstance(jti_raw, str) or not jti_raw.strip():
            raise TokenDecodeError("Поле jti должно быть непустой строкой.")

        iat = self._to_utc_datetime(decoded_payload.get("iat"), "iat")
        exp = self._to_utc_datetime(decoded_payload.get("exp"), "exp")

        return AccessTokenPayload(
            sub=sub,
            jti=jti_raw,
            iat=iat,
            exp=exp,
            token_type="access",
        )

    def create_refresh_token(self) -> str:
        return secrets.token_urlsafe(48)

    def hash_refresh_token(self, raw_token: str) -> str:
        if not raw_token.strip():
            raise ValueError("raw_token не должен быть пустым.")

        return hmac.new(
            key=self._settings.refresh_token_hash_secret.encode("utf-8"),
            msg=raw_token.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
