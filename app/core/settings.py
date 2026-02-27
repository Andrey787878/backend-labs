from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    locale: str = Field(default="ru", validation_alias="APP_LOCALE")
    timezone: str = Field(default="Europe/Moscow", validation_alias="APP_TIMEZONE")
    database_url: str

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid timezone: {value}") from exc
        return value

settings = Settings()