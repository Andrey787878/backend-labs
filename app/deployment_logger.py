from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DeploymentLogger:
    """Пишет структурированные deployment-логи без секретных данных."""

    def __init__(self, project_root: Path) -> None:
        self._log_dir = project_root / "deployment_logs"
        self._log_file = self._log_dir / "deployment.log"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **payload: Any) -> None:
        """Добавляет одну JSON-строку в deployment.log."""
        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        self._log_dir.mkdir(parents=True, exist_ok=True)
        with self._log_file.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log_start(self, client_ip: str | None) -> None:
        """Логирует начало deployment-операции."""
        self.log("deployment_start", status="started", client_ip=client_ip)

    def log_finish(self, status: str, message: str) -> None:
        """Логирует завершение deployment-операции."""
        self.log("deployment_finish", status=status, message=message)
