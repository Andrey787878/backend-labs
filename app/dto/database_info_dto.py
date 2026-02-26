from pydantic import BaseModel, ConfigDict

class DatabaseInfoDTO(BaseModel):
    model_config = ConfigDict(frozen=True)  # "неизменяемый"
    driver: str
    server_version: str
    database: str