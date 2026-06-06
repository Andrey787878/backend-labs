from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.db import SessionLocal
from app.request_log_service import RequestLogService


logger = logging.getLogger(__name__)


async def run_request_log_cleanup_scheduler(
    *,
    retention_hours: int,
    interval_seconds: int,
) -> None:
    """Периодически удаляет request/response логи старше retention_hours."""
    while True:
        await asyncio.sleep(interval_seconds)
        deleted_count = await asyncio.to_thread(_delete_old_logs, retention_hours)
        logger.info("Deleted old request logs by scheduler: %s", deleted_count)


async def stop_request_log_cleanup_scheduler(task: asyncio.Task[None]) -> None:
    """Останавливает background scheduler при завершении приложения."""
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def _delete_old_logs(retention_hours: int) -> int:
    """Синхронно удаляет старые логи в отдельной DB-сессии."""
    with SessionLocal() as db:
        return RequestLogService(db).delete_older_than(retention_hours)
