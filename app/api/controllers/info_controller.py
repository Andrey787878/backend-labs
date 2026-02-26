from fastapi import Request
from app.dto.server_info_dto import ServerInfoDTO
from app.dto.client_info_dto import ClientInfoDTO
from app.dto.database_info_dto import DatabaseInfoDTO
from app.db.session import get_db_info

class InfoController:
    def server_info(self) -> ServerInfoDTO:
        return ServerInfoDTO.from_runtime()

    def client_info(self, request: Request) -> ClientInfoDTO:
        # X-Forwarded-For может быть, если потом будет прокси
        forwarded = request.headers.get("x-forwarded-for")
        ip = (forwarded.split(",")[0].strip() if forwarded else request.client.host)
        return ClientInfoDTO(ip=ip, user_agent=request.headers.get("user-agent"))

    def database_info(self) -> DatabaseInfoDTO:
        info = get_db_info()
        return DatabaseInfoDTO(**info)