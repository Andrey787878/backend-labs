from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LoginInputDTO(BaseModel):
    """Входные данные для логина."""

    model_config = ConfigDict(frozen=True)

    username: str
    password: str


class RegisterInputDTO(BaseModel):
    """Входные данные для регистрации."""

    model_config = ConfigDict(frozen=True)

    username: str
    email: str
    password: str
    birthday: date


class RefreshInputDTO(BaseModel):
    """Входные данные для обновления токенов."""

    model_config = ConfigDict(frozen=True)

    refresh_token: str


class ChangePasswordInputDTO(BaseModel):
    """Входные данные для смены пароля."""

    model_config = ConfigDict(frozen=True)

    current_password: str
    new_password: str


class UserDTO(BaseModel):
    """Публичные данные пользователя."""

    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    email: str
    birthday: date


class AuthSuccessDTO(BaseModel):
    """Успешная авторизации."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    user: UserDTO


class TokenMetaDTO(BaseModel):
    """Метаданные одной сессии."""

    model_config = ConfigDict(frozen=True)

    id: int
    created_at: datetime
    last_used_at: datetime | None
    access_expires_at: datetime
    refresh_expires_at: datetime
    ip: str | None
    user_agent: str | None
    revoked_at: datetime | None
    revoked_reason: str | None


class TokenListDTO(BaseModel):
    """Список сессий пользователя."""

    model_config = ConfigDict(frozen=True)

    items: list[TokenMetaDTO]


class MessageResponseDTO(BaseModel):
    """Сервисный ответ с результатом операции."""

    model_config = ConfigDict(frozen=True)

    message: str


class LogoutAllResponseDTO(BaseModel):
    """Выход везде."""

    model_config = ConfigDict(frozen=True)

    message: str
    revoked_count: int
