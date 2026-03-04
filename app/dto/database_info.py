from pydantic import BaseModel, ConfigDict


class DatabaseInfoDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    driver: str
    server_version: str
    database_name: str
