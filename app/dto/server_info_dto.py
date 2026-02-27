from datetime import datetime
import platform
import sys
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict

class ServerInfoDTO(BaseModel):
    model_config = ConfigDict(frozen=True)
    python_version: str
    implementation: str
    platform: str
    timezone: str
    server_time: str

    @staticmethod
    def from_runtime(timezone: str) -> "ServerInfoDTO":
        local_time = datetime.now(ZoneInfo(timezone))
        return ServerInfoDTO(
            python_version=sys.version.split()[0],
            implementation=platform.python_implementation(),
            platform=platform.platform(),
            timezone=timezone,
            server_time=local_time.isoformat(),
        )
