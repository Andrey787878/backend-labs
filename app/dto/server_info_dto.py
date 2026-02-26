import platform
import sys
from pydantic import BaseModel, ConfigDict

class ServerInfoDTO(BaseModel):
    model_config = ConfigDict(frozen=True)
    python_version: str
    implementation: str
    platform: str

    @staticmethod
    def from_runtime() -> "ServerInfoDTO":
        return ServerInfoDTO(
            python_version=sys.version.split()[0],
            implementation=platform.python_implementation(),
            platform=platform.platform(),
        )