import os
import time
import ipaddress
import platform
import re

import fastapi as fastapi_pkg
from fastapi import FastAPI, HTTPException, Request, status
from sqlalchemy import create_engine

from app.config import settings
from app.dto.client_info import ClientInfoDTO
from app.dto.database_info import DatabaseInfoDTO
from app.dto.server_info import ServerInfoDTO
from app.services.database_info_service import load_database_info


MAX_USER_AGENT_LENGTH = 255
# Фильтьр управляющих символов
_CONTROL_CHARS = re.compile(r"[\x00-\x1F\x7F]")
# Фильтр XSS/JS
_UNSAFE_PAYLOAD = re.compile(r"(<|>|javascript:|%3c|%3e|<\s*script|\bon\w+\s*=)", re.IGNORECASE)

engine = create_engine(settings.database_url, pool_pre_ping=True)

app = FastAPI()

def parse_ip(raw_value: str | None) -> str:
    if raw_value is None:
        return "unknown"
    value = raw_value.strip()
    if not value:
        return "unknown"
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client IP address.",
        ) from error


def validate_user_agent(raw_value: str | None) -> str:
    if raw_value is None:
        return "unknown"
    value = raw_value.strip()
    if not value:
        return "unknown"
    if len(value) > MAX_USER_AGENT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid User-Agent: too long.",
        )
    if _CONTROL_CHARS.search(value) or _UNSAFE_PAYLOAD.search(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid User-Agent: unsafe value.",
        )
    return value


@app.get("/info/server", response_model=ServerInfoDTO)
def server_info() -> ServerInfoDTO:
    return ServerInfoDTO(
        python_version=platform.python_version(),
        fastapi_version=fastapi_pkg.__version__,
        app_locale=settings.app_locale,
        app_timezone=settings.app_timezone,
    )


@app.get("/info/client", response_model=ClientInfoDTO)
def client_info(request: Request) -> ClientInfoDTO:
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ClientInfoDTO(
        ip=parse_ip(client_host),
        user_agent=validate_user_agent(user_agent),
    )


@app.get("/info/database", response_model=DatabaseInfoDTO)
def database_info() -> DatabaseInfoDTO:
    driver, server_version, database_name = load_database_info(engine)
    return DatabaseInfoDTO(
        driver=driver,
        server_version=server_version,
        database_name=database_name,
    )
