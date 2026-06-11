from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.attendance_calculator import AttendanceCalculator
from app.attendance_file_parser import AttendanceFileParser, AttendanceParseError
from app.attendance_response_builder import AttendanceResponseBuilder
from app.config import Settings, get_settings
from app.dto import AttendanceCalculateResponseDTO
from app.dependencies import require_permission
from app.rbac_permissions import PermissionSlugs


UPLOAD_READ_CHUNK_SIZE_BYTES = 1024 * 1024

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


def _raise_validation_error(message: str) -> NoReturn:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)


async def _read_limited_upload_file(
    file: UploadFile,
    *,
    max_size_bytes: int,
    max_size_mb: int,
) -> bytes:
    """Читает файл по частям и останавливается сразу после превышения лимита."""
    chunks: list[bytes] = []
    total_size = 0

    while chunk := await file.read(UPLOAD_READ_CHUNK_SIZE_BYTES):
        total_size += len(chunk)
        if total_size > max_size_bytes:
            _raise_validation_error(f"Размер файла не должен превышать {max_size_mb} МБ.")
        chunks.append(chunk)

    if not chunks:
        _raise_validation_error("Файл не должен быть пустым.")

    return b"".join(chunks)


@router.post(
    "/calculate",
    summary="Рассчитать автоматический зачёт по файлу посещаемости",
    description=(
        "ЛР12: принимает Excel-файл .xlsx с листом 'Посещаемость', рассчитывает процент "
        "посещаемости, процент выполненных лабораторных и определяет студентов, которые "
        "получают зачёт автоматически."
    ),
    response_model=AttendanceCalculateResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.CALCULATE_ATTENDANCE))],
    responses={
        status.HTTP_200_OK: {"description": "Расчёт выполнен, JSON-отчёт сформирован."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Пользователь не авторизован."},
        status.HTTP_403_FORBIDDEN: {"description": "Недостаточно прав calculate-attendance."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Ошибка файла или формата данных."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Внутренняя ошибка расчёта."},
    },
)
async def calculate_attendance(
    file: UploadFile = File(..., description="Excel-файл .xlsx с листом 'Посещаемость'."),
    settings: Settings = Depends(get_settings),
) -> AttendanceCalculateResponseDTO:
    """Загружает .xlsx и возвращает JSON-расчёт автоматического зачёта."""
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        _raise_validation_error("Файл должен иметь расширение .xlsx.")

    max_size_bytes = settings.upload_max_size_mb * 1024 * 1024
    file_content = await _read_limited_upload_file(
        file,
        max_size_bytes=max_size_bytes,
        max_size_mb=settings.upload_max_size_mb,
    )

    try:
        rows = AttendanceFileParser().parse(file_content)
    except AttendanceParseError as exc:
        _raise_validation_error(str(exc))

    calculated_students = AttendanceCalculator(
        required_labs=settings.required_labs,
        attendance_percent_threshold=settings.attendance_percent_threshold,
    ).calculate(rows)
    return AttendanceResponseBuilder().build(calculated_students)
