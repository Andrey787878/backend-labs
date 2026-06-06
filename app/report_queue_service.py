from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.dto import ReportGenerateResponseDTO, ReportJobDTO
from app.models import ReportJob


REPORT_JOB_STATUS_QUEUED = "queued"
REPORT_JOB_STATUS_RUNNING = "running"
REPORT_JOB_STATUS_SUCCEEDED = "succeeded"
REPORT_JOB_STATUS_FAILED = "failed"


class ReportJobNotFoundError(Exception):
    """Задача генерации отчёта не найдена."""


class ReportQueueService:
    """DB-backed очередь задач генерации аналитических отчётов."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def enqueue_report(self, *, created_by: int, max_attempts: int) -> ReportGenerateResponseDTO:
        """Создаёт queued job и возвращает DTO для HTTP-ответа."""
        job = ReportJob(
            status=REPORT_JOB_STATUS_QUEUED,
            attempts=0,
            max_attempts=max_attempts,
            created_by=created_by,
        )
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return ReportGenerateResponseDTO(
            message="Отчёт поставлен в очередь на генерацию.",
            job_id=job.id,
            status=job.status,
        )

    def fetch_and_mark_running(self) -> ReportJob | None:
        """Берёт ближайшую queued job и переводит её в running."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(ReportJob)
            .where(
                ReportJob.status == REPORT_JOB_STATUS_QUEUED,
                or_(ReportJob.run_after.is_(None), ReportJob.run_after <= now),
            )
            .order_by(ReportJob.created_at.asc(), ReportJob.id.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = self._db.scalar(stmt)
        if job is None:
            return None

        job.status = REPORT_JOB_STATUS_RUNNING
        job.attempts += 1
        job.started_at = now
        job.updated_at = now
        job.error_message = None
        self._db.commit()
        self._db.refresh(job)
        return job

    def mark_succeeded(self, *, job_id: int, report_path: str) -> ReportJobDTO:
        """Помечает job как успешно выполненную."""
        job = self._get_job(job_id)
        now = datetime.now(timezone.utc)
        job.status = REPORT_JOB_STATUS_SUCCEEDED
        job.report_path = report_path
        job.finished_at = now
        job.updated_at = now
        job.error_message = None
        self._db.commit()
        self._db.refresh(job)
        return self.to_dto(job)

    def mark_failed_or_retry(
        self,
        *,
        job_id: int,
        error_message: str,
        retry_delay_minutes: int,
    ) -> ReportJobDTO:
        """Помечает job failed или возвращает её в queued с backoff."""
        job = self._get_job(job_id)
        now = datetime.now(timezone.utc)
        job.error_message = error_message[:4000]
        job.updated_at = now

        if job.attempts < job.max_attempts:
            job.status = REPORT_JOB_STATUS_QUEUED
            job.run_after = now + timedelta(minutes=retry_delay_minutes)
            job.started_at = None
        else:
            job.status = REPORT_JOB_STATUS_FAILED
            job.finished_at = now

        self._db.commit()
        self._db.refresh(job)
        return self.to_dto(job)

    def to_dto(self, job: ReportJob) -> ReportJobDTO:
        """Преобразует ORM-модель report job в DTO."""
        return ReportJobDTO(
            id=job.id,
            status=job.status,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            report_path=job.report_path,
            error_message=job.error_message,
            created_by=job.created_by,
            created_at=job.created_at,
        )

    def _get_job(self, job_id: int) -> ReportJob:
        job = self._db.get(ReportJob, job_id)
        if job is None:
            raise ReportJobNotFoundError(f"Report job #{job_id} не найдена.")
        return job
