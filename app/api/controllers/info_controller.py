from fastapi import Request
from app.dto.server_info_dto import ServerInfoDTO
from app.dto.client_info_dto import ClientInfoDTO
from app.dto.database_info_dto import DatabaseInfoDTO
from app.db.session import get_db_info
from app.core.settings import settings

class InfoController:
    def server_info(self) -> ServerInfoDTO:
        return ServerInfoDTO.from_runtime(settings.timezone)

    def client_info(self, request: Request) -> ClientInfoDTO:
        # Если есть прокси - берем первый IP из X-Forwarded-For
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            # Иначе используем прямой адрес клиента
            client_ip = request.client.host if request.client else "unknown"

        # User-Agent может отсутствовать, поэтому поле nullable
        user_agent = request.headers.get("user-agent")
        return ClientInfoDTO(ip=client_ip, user_agent=user_agent)

    def database_info(self) -> DatabaseInfoDTO:
        db_info = get_db_info()
        return DatabaseInfoDTO(**db_info)