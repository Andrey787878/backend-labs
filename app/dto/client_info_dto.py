from pydantic import BaseModel, ConfigDict

class ClientInfoDTO(BaseModel):
    model_config = ConfigDict(frozen=True)
    ip: str
    user_agent: str | None