from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    locale: str = "ru"
    timezone: str = "Europe/Moscow"
    database_url: str

settings = Settings()