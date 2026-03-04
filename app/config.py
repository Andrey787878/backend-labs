import re
from zoneinfo import available_timezones

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Фильтр XSS/JS
_UNSAFE_PAYLOAD = re.compile(r"(<|>|javascript:|%3c|%3e|<\s*script|\bon\w+\s*=)", re.IGNORECASE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    app_locale: str = Field(default="ru", validation_alias="APP_LOCALE")
    app_timezone: str = Field(default="Europe/Moscow", validation_alias="APP_TIMEZONE")
    database_url: str = Field(validation_alias="DATABASE_URL")

    @field_validator("app_locale")
    @classmethod
    def validate_locale(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("APP_LOCALE must not be empty.")
        if _UNSAFE_PAYLOAD.search(normalized):
            raise ValueError("APP_LOCALE contains unsafe characters.")
        return normalized

    @field_validator("app_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("APP_TIMEZONE must not be empty.")
        if _UNSAFE_PAYLOAD.search(normalized):
            raise ValueError("APP_TIMEZONE contains unsafe characters.")
        if normalized not in available_timezones():
            raise ValueError("APP_TIMEZONE must be a valid IANA timezone, for example Europe/Moscow.")
        return normalized

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("DATABASE_URL must not be empty.")
        if _UNSAFE_PAYLOAD.search(normalized):
            raise ValueError("DATABASE_URL contains unsafe characters.")
        if not normalized.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must start with postgresql+psycopg://")
        return normalized

settings = Settings()
