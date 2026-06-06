from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db import SessionLocal
from app.report_builder import ReportBuilder
from app.report_data_collector import ReportDataCollector
from app.report_queue_service import ReportQueueService
from app.report_sender import ReportSender


logger = logging.getLogger(__name__)


class ReportJobProcessor:
    """Выполняет одну queued job генерации аналитического отчёта."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def process_next_job(self) -> bool:
        """Обрабатывает одну доступную job и возвращает True, если job была найдена."""
        with SessionLocal() as db:
            queue = ReportQueueService(db)
            try:
                job = queue.fetch_and_mark_running()
            except SQLAlchemyError:
                logger.warning("Analytics report queue is unavailable. Check database migrations.")
                return False

            if job is None:
                return False

            logger.info("Started analytics report job #%s", job.id)
            try:
                content = ReportDataCollector(db).collect(
                    interval_hours=self._settings.report_time_interval_hours,
                )
                report_path = ReportBuilder(self._settings.reports_dir).build_json_report(
                    job_id=job.id,
                    content=content,
                )
                ReportSender(self._settings.report_admin_email).send(report_path=report_path)
                queue.mark_succeeded(job_id=job.id, report_path=report_path)
                logger.info("Finished analytics report job #%s: %s", job.id, report_path)
                return True
            except Exception as exc:
                queue.mark_failed_or_retry(
                    job_id=job.id,
                    error_message=str(exc),
                    retry_delay_minutes=self._settings.report_job_retry_delay_minutes,
                )
                logger.exception("Failed analytics report job #%s", job.id)
                return True
