from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


class ReportSender:
    """Эмулирует доставку отчёта администраторам в лабораторном окружении."""

    def __init__(self, admin_email: str) -> None:
        self._admin_email = admin_email

    def send(self, *, report_path: str) -> None:
        """Логирует получателей и путь к готовому отчёту."""
        logger.info("Analytics report is ready for %s: %s", self._admin_email, report_path)
