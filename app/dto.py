from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ==================== ЛР2: Авторизация ====================
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


# ==================== ЛР3: RBAC ====================
class RoleWriteDTO(BaseModel):
    """Входные данные для создания/обновления роли."""

    model_config = ConfigDict(frozen=True)

    name: str
    slug: str
    description: str | None


class RoleUpdateDTO(BaseModel):
    """Входные данные для частичного обновления роли."""

    model_config = ConfigDict(frozen=True)

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    has_name: bool = False
    has_slug: bool = False
    has_description: bool = False


class PermissionWriteDTO(BaseModel):
    """Входные данные для создания/обновления разрешения."""

    model_config = ConfigDict(frozen=True)

    name: str
    slug: str
    description: str | None


class PermissionUpdateDTO(BaseModel):
    """Входные данные для частичного обновления разрешения."""

    model_config = ConfigDict(frozen=True)

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    has_name: bool = False
    has_slug: bool = False
    has_description: bool = False


class AttachUserRoleDTO(BaseModel):
    """Входные данные для назначения роли пользователю."""

    model_config = ConfigDict(frozen=True)

    role_id: int


class AttachRolePermissionDTO(BaseModel):
    """Входные данные для назначения разрешения роли."""

    model_config = ConfigDict(frozen=True)

    permission_id: int


class UserUpdateDTO(BaseModel):
    """Входные данные для частичного обновления пользователя администратором."""

    model_config = ConfigDict(frozen=True)

    username: str | None = None
    email: str | None = None
    birthday: date | None = None
    has_username: bool = False
    has_email: bool = False
    has_birthday: bool = False


class RoleDTO(BaseModel):
    """Публичные данные роли."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    slug: str
    description: str | None
    created_at: datetime
    created_by: int
    deleted_at: datetime | None
    deleted_by: int | None


class RoleCollectionDTO(BaseModel):
    """Коллекция ролей."""

    model_config = ConfigDict(frozen=True)

    items: list[RoleDTO]
    total: int = Field(ge=0)


class PermissionDTO(BaseModel):
    """Публичные данные разрешения."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    slug: str
    description: str | None
    created_at: datetime
    created_by: int
    deleted_at: datetime | None
    deleted_by: int | None


class PermissionCollectionDTO(BaseModel):
    """Коллекция разрешений."""

    model_config = ConfigDict(frozen=True)

    items: list[PermissionDTO]
    total: int = Field(ge=0)


# ==================== ЛР2: Авторизация (расширено ролями ЛР3) ====================
class UserDTO(BaseModel):
    """Публичные данные пользователя."""

    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    email: str
    birthday: date
    roles: list[RoleDTO] = Field(default_factory=list)


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


# ==================== ЛР4: Audit DTO ====================
class ChangedFieldDTO(BaseModel):
    """Измененное поле в истории мутаций."""

    model_config = ConfigDict(frozen=True)

    old: Any = None
    new: Any = None


class ChangeLogDTO(BaseModel):
    """DTO одной записи истории изменений."""

    model_config = ConfigDict(frozen=True)

    id: int
    entity_type: str
    entity_id: int
    changed_fields: dict[str, ChangedFieldDTO]
    created_at: datetime
    created_by: int


class ChangeLogCollectionDTO(BaseModel):
    """DTO коллекции истории изменений."""

    model_config = ConfigDict(frozen=True)

    items: list[ChangeLogDTO]
    total: int = Field(ge=0)


# ==================== ЛР6: Git Webhook Deployment DTO ====================
class GitCommandResultDTO(BaseModel):
    """Результат выполнения одной Git-команды."""

    model_config = ConfigDict(frozen=True)

    command: str = Field(description="Выполненная Git-команда.")
    return_code: int = Field(description="Код завершения процесса.")
    stdout: str = Field(description="Стандартный вывод команды.")
    stderr: str = Field(description="Стандартный поток ошибок команды.")


class DeploymentResponseDTO(BaseModel):
    """Ответ webhook-а после завершения deployment-операции."""

    model_config = ConfigDict(frozen=True)

    message: str = Field(description="Итоговое сообщение deployment-процесса.")
    branch: str = Field(description="Git-ветка, которая обновлялась.")
    commands: list[GitCommandResultDTO] = Field(
        default_factory=list,
        description="Результаты выполненных Git-команд.",
    )


# ==================== ЛР7: Request/Response Logging DTO ====================
class LogRequestDTO(BaseModel):
    """Полная запись request/response лога."""

    model_config = ConfigDict(frozen=True)

    id: int
    full_url: str
    method: str
    controller_path: str | None
    controller_method: str | None
    request_body: dict[str, Any] | None
    request_headers: dict[str, Any] | None
    user_id: int | None
    ip_address: str | None
    user_agent: str | None
    response_status: int
    response_body: dict[str, Any] | None
    response_headers: dict[str, Any] | None
    called_at: datetime
    created_at: datetime


class LogRequestListItemDTO(BaseModel):
    """Сокращённая запись request/response лога для списка."""

    model_config = ConfigDict(frozen=True)

    id: int
    full_url: str
    method: str
    controller_path: str | None
    controller_method: str | None
    response_status: int
    called_at: datetime


class LogRequestCollectionDTO(BaseModel):
    """Коллекция request/response логов с мета-информацией пагинации."""

    model_config = ConfigDict(frozen=True)

    items: list[LogRequestListItemDTO]
    page: int = Field(ge=1)
    pages: int = Field(ge=0)
    total: int = Field(ge=0)
    count: int = Field(ge=1)


# ==================== ЛР8: Queued Analytics Reports DTO ====================
class ReportGenerateResponseDTO(BaseModel):
    """Ответ постановки аналитического отчёта в очередь."""

    model_config = ConfigDict(frozen=True)

    message: str = Field(description="Итоговое сообщение операции.")
    job_id: int = Field(description="Идентификатор фоновой задачи.")
    status: str = Field(description="Текущий статус задачи.")


class ReportJobDTO(BaseModel):
    """Публичное состояние задачи генерации отчёта."""

    model_config = ConfigDict(frozen=True)

    id: int
    status: str
    attempts: int
    max_attempts: int
    report_path: str | None
    error_message: str | None
    created_by: int | None
    created_at: datetime


class ReportRatingItemDTO(BaseModel):
    """Одна строка рейтинга методов или сущностей."""

    model_config = ConfigDict(frozen=True)

    name: str
    count: int = Field(ge=0)
    last_operation_at: datetime | None


class ReportUserRatingItemDTO(BaseModel):
    """Одна строка пользовательского рейтинга."""

    model_config = ConfigDict(frozen=True)

    user_id: int
    request_count: int = Field(ge=0)
    change_count: int = Field(ge=0)
    auth_count: int = Field(ge=0)
    permission_count: int = Field(ge=0)
    last_operation_at: datetime | None


class ReportPeriodDTO(BaseModel):
    """Период, за который собран аналитический отчёт."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    from_at: datetime = Field(alias="from")
    to: datetime
    hours: int = Field(ge=1)


class ReportContentDTO(BaseModel):
    """Структура JSON-отчёта ЛР8."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    type: str
    generated_at: datetime
    period: ReportPeriodDTO
    method_rating: list[ReportRatingItemDTO]
    entity_rating: list[ReportRatingItemDTO]
    user_rating: list[ReportUserRatingItemDTO]


class LogoutAllResponseDTO(BaseModel):
    """Выход везде."""

    model_config = ConfigDict(frozen=True)

    message: str
    revoked_count: int
