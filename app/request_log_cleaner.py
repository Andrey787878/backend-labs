from __future__ import annotations

from app.config import get_settings
from app.db import SessionLocal
from app.request_log_service import RequestLogService


def clean_old_request_logs() -> int:
    """Удаляет request/response логи старше configured retention и возвращает количество."""
    settings = get_settings()
    with SessionLocal() as db:
        return RequestLogService(db).delete_older_than(settings.request_log_retention_hours)


def main() -> None:
    """CLI-вход для ручного или cron-запуска очистки старых request/response логов."""
    deleted_count = clean_old_request_logs()
    print(f"Deleted old request logs: {deleted_count}")


if __name__ == "__main__":
    main()
