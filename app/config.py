from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


HS256_MIN_SECRET_BYTES = 32
GIT_WEBHOOK_SECRET_LENGTH = 36


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    postgres_db: str = Field(default="app", alias="POSTGRES_DB")
    postgres_user: str = Field(default="app", alias="POSTGRES_USER")
    postgres_password: str = Field(default="app", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="db", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT", ge=1)

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT", ge=1)

    jwt_secret: str = Field(
        ...,
        alias="JWT_SECRET",
        min_length=32,
    )
    jwt_algorithm: Literal["HS256"] = Field(
        default="HS256",
        alias="JWT_ALGORITHM",
    )
    refresh_token_pepper: str | None = Field(
        default=None,
        alias="REFRESH_TOKEN_PEPPER",
    )

    access_token_ttl_minutes: int = Field(
        default=15,
        alias="ACCESS_TOKEN_TTL_MINUTES",
        ge=1,
    )
    refresh_token_ttl_minutes: int = Field(
        default=10080,
        alias="REFRESH_TOKEN_TTL_MINUTES",
        ge=1,
    )
    max_active_sessions: int = Field(
        default=5,
        alias="MAX_ACTIVE_SESSIONS",
        ge=1,
    )

    # ==================== ЛР6: Git Webhook Deployment ====================
    git_webhook_secret: str = Field(
        ...,
        alias="GIT_WEBHOOK_SECRET",
        min_length=GIT_WEBHOOK_SECRET_LENGTH,
        max_length=GIT_WEBHOOK_SECRET_LENGTH,
    )
    git_default_branch: str = Field(default="main", alias="GIT_DEFAULT_BRANCH", min_length=1)
    git_webhook_lock_ttl_seconds: int = Field(
        default=300,
        alias="GIT_WEBHOOK_LOCK_TTL_SECONDS",
        ge=1,
    )
    git_webhook_command_timeout_seconds: int = Field(
        default=120,
        alias="GIT_WEBHOOK_COMMAND_TIMEOUT_SECONDS",
        ge=1,
    )

    # ==================== ЛР7: Request/Response Logging ====================
    request_log_retention_hours: int = Field(default=73, alias="REQUEST_LOG_RETENTION_HOURS", ge=1)
    request_log_body_max_chars: int = Field(default=20000, alias="REQUEST_LOG_BODY_MAX_CHARS", ge=1000)
    request_log_clean_interval_seconds: int = Field(
        default=3600,
        alias="REQUEST_LOG_CLEAN_INTERVAL_SECONDS",
        ge=60,
    )

    # ==================== ЛР8: Queued Analytics Reports ====================
    report_time_interval_hours: int = Field(default=24, alias="REPORT_TIME_INTERVAL_HOURS", ge=1)
    report_job_timeout_minutes: int = Field(default=5, alias="REPORT_JOB_TIMEOUT_MINUTES", ge=1)
    report_job_retry_delay_minutes: int = Field(
        default=2,
        alias="REPORT_JOB_RETRY_DELAY_MINUTES",
        ge=1,
    )
    report_job_max_attempts: int = Field(default=3, alias="REPORT_JOB_MAX_ATTEMPTS", ge=1)
    report_admin_email: str = Field(default="admin@example.com", alias="REPORT_ADMIN_EMAIL")
    report_worker_poll_interval_seconds: int = Field(
        default=5,
        alias="REPORT_WORKER_POLL_INTERVAL_SECONDS",
        ge=1,
    )
    reports_dir: str = Field(default="reports", alias="REPORTS_DIR", min_length=1)

    # ==================== ЛР12: Attendance Auto Credit ====================
    required_labs: int = Field(default=5, alias="REQUIRED_LABS", ge=1)
    attendance_percent_threshold: int = Field(
        default=80,
        alias="ATTENDANCE_PERCENT_THRESHOLD",
        ge=0,
        le=100,
    )
    upload_max_size_mb: int = Field(default=10, alias="UPLOAD_MAX_SIZE_MB", ge=1)

    @field_validator("refresh_token_pepper", mode="before")
    @classmethod
    def parse_refresh_token_pepper(cls, raw_value: Any) -> str | None:
        if raw_value is None:
            raise ValueError(
                "REFRESH_TOKEN_PEPPER должен быть задан. "
                "Этот секрет используется только для хеширования refresh token."
            )
        if isinstance(raw_value, str):
            value = raw_value.strip()
            if not value:
                raise ValueError("REFRESH_TOKEN_PEPPER не должен быть пустым.")
            if len(value) < 16:
                raise ValueError("REFRESH_TOKEN_PEPPER должен содержать минимум 16 символов.")
            return value
        raise TypeError("REFRESH_TOKEN_PEPPER должен быть строкой.")

    @model_validator(mode="after")
    def validate_refresh_hash_secret(self) -> "Settings":
        if self.refresh_token_pepper is None:
            raise ValueError(
                "REFRESH_TOKEN_PEPPER должен быть задан в окружении для запуска приложения."
            )
        return self

    @model_validator(mode="after")
    def validate_jwt_secret_strength(self) -> "Settings":
        secret_length_bytes = len(self.jwt_secret.encode("utf-8"))
        if secret_length_bytes < HS256_MIN_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET слишком короткий для HS256: "
                f"нужно минимум {HS256_MIN_SECRET_BYTES} байт."
            )
        return self

    @field_validator("git_webhook_secret")
    @classmethod
    def validate_git_webhook_secret(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) != GIT_WEBHOOK_SECRET_LENGTH:
            raise ValueError("GIT_WEBHOOK_SECRET должен содержать ровно 36 символов.")
        return normalized

    @field_validator("git_default_branch")
    @classmethod
    def validate_git_default_branch(cls, value: str) -> str:
        """Проверяет, что ветка из .env является безопасным Git ref."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("GIT_DEFAULT_BRANCH не должен быть пустым.")
        if any(char.isspace() for char in normalized):
            raise ValueError("GIT_DEFAULT_BRANCH не должен содержать пробельные символы.")
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-")
        if normalized.startswith("-") or not set(normalized) <= allowed_chars:
            raise ValueError("GIT_DEFAULT_BRANCH содержит недопустимые символы.")
        if normalized.endswith("/") or ".." in normalized or "@{" in normalized:
            raise ValueError("GIT_DEFAULT_BRANCH должен быть корректным именем Git-ветки.")
        return normalized

    @field_validator("report_admin_email")
    @classmethod
    def validate_report_admin_email(cls, value: str) -> str:
        """Проверяет, что список получателей отчёта не пустой."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("REPORT_ADMIN_EMAIL не должен быть пустым.")
        return normalized

    @field_validator("reports_dir")
    @classmethod
    def validate_reports_dir(cls, value: str) -> str:
        """Нормализует директорию хранения отчётов."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("REPORTS_DIR не должен быть пустым.")
        return normalized

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def refresh_token_hash_secret(self) -> str:
        if self.refresh_token_pepper is None:
            raise ValueError(
                "Ошибка конфигурации: REFRESH_TOKEN_PEPPER должен быть задан "
                "и не может быть пустым."
            )
        return self.refresh_token_pepper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
