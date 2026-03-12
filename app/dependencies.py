from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth_service import AuthService
from app.db import get_db
from app.models import AuthSession
from app.token_service import (
    AccessTokenPayload,
    TokenDecodeError,
    TokenHeaderError,
    TokenService,
)


@dataclass(frozen=True)
class CurrentUserContext:
    user_id: int
    access_jti: str
    session_id: int
    payload: AccessTokenPayload


def get_token_service() -> TokenService:
    return TokenService()


def get_auth_service(
    db: Session = Depends(get_db),
    token_service: TokenService = Depends(get_token_service),
) -> AuthService:
    return AuthService(db=db, token_service=token_service)


def ensure_guest_only(
    authorization: str | None = Header(default=None, alias="Authorization"),
    token_service: TokenService = Depends(get_token_service),
    db: Session = Depends(get_db),
) -> None:
    if authorization is None or not authorization.strip():
        return

    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return

    try:
        header = token_service.parse_jwt_header(token.strip())
        token_service.validate_jwt_header(header)
        payload = token_service.decode_access_token(token.strip())
    except (TokenHeaderError, TokenDecodeError):
        return

    try:
        session = db.scalar(select(AuthSession).where(AuthSession.access_jti == payload.jti))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к данным. Повторите попытку позже.",
        ) from exc
    if session is None or session.user_id != payload.sub:
        return

    now = datetime.now(timezone.utc)
    if session.revoked_at is not None or session.refresh_expires_at <= now:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Маршрут доступен только неавторизованным пользователям.",
    )


def _extract_bearer_token(authorization: str | None) -> str:
    """Извлекает токен из заголовка Authorization в формате Bearer."""
    if authorization is None or not authorization.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Отсутствует заголовок Authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ожидается формат Authorization: Bearer <token>.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token.strip()


def get_current_access_payload(
    authorization: str | None = Header(default=None, alias="Authorization"),
    token_service: TokenService = Depends(get_token_service),
) -> AccessTokenPayload:
    """Проверяет Bearer access token и возвращает декодированный payload."""
    token = _extract_bearer_token(authorization)

    try:
        header = token_service.parse_jwt_header(token)
        token_service.validate_jwt_header(header)
        return token_service.decode_access_token(token)
    except (TokenHeaderError, TokenDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user_context(
    payload: AccessTokenPayload = Depends(get_current_access_payload),
    db: Session = Depends(get_db),
) -> CurrentUserContext:
    """Проверяет server-side состояние сессии и возвращает контекст пользователя."""
    try:
        session = db.scalar(select(AuthSession).where(AuthSession.access_jti == payload.jti))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к данным. Повторите попытку позже.",
        ) from exc
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия для access token не найдена.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if session.user_id != payload.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token не соответствует пользователю сессии.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Текущая сессия отозвана.",
        )

    now = datetime.now(timezone.utc)
    if session.refresh_expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Сессия истекла.",
        )

    return CurrentUserContext(
        user_id=session.user_id,
        access_jti=session.access_jti,
        session_id=session.id,
        payload=payload,
    )
