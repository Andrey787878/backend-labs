from fastapi import APIRouter, Request
from app.api.controllers.info_controller import InfoController
from app.dto.server_info_dto import ServerInfoDTO
from app.dto.client_info_dto import ClientInfoDTO
from app.dto.database_info_dto import DatabaseInfoDTO

router = APIRouter()
controller = InfoController()

@router.get("/info/server", response_model=ServerInfoDTO)
def server_info():
    return controller.server_info()

@router.get("/info/client", response_model=ClientInfoDTO)
def client_info(request: Request):
    return controller.client_info(request)

@router.get("/info/database", response_model=DatabaseInfoDTO)
def database_info():
    return controller.database_info()