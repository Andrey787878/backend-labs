from __future__ import annotations

import json
from pathlib import Path

from app.dto import ReportContentDTO


class ReportBuilder:
    """Формирует JSON-файл аналитического отчёта."""

    def __init__(self, reports_dir: str) -> None:
        self._reports_dir = Path(reports_dir)
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    def build_json_report(self, *, job_id: int, content: ReportContentDTO) -> str:
        """Сохраняет JSON report и возвращает путь к файлу."""
        report_path = self._reports_dir / f"analytics_report_{job_id}.json"
        payload = content.model_dump(mode="json", by_alias=True)
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(report_path)
