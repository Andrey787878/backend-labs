from pydantic import BaseModel, ConfigDict


class ServerInfoDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    python_version: str
    fastapi_version: str
    app_locale: str
    app_timezone: str
