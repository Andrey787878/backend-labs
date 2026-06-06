from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.config import Settings
from app.report_job_processor import ReportJobProcessor


logger = logging.getLogger(__name__)


async def run_report_worker(settings: Settings) -> None:
    """Периодически обрабатывает queued report jobs в фоне."""
    timeout_seconds = settings.report_job_timeout_minutes * 60
    processor = ReportJobProcessor(settings)

    while True:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(processor.process_next_job),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            logger.exception("Analytics report worker timeout")
        except Exception:
            logger.exception("Analytics report worker error")

        await asyncio.sleep(settings.report_worker_poll_interval_seconds)


async def stop_report_worker(task: asyncio.Task[None]) -> None:
    """Останавливает background report worker при shutdown приложения."""
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
