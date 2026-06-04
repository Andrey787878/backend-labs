from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from app.dto import GitCommandResultDTO


class GitCommandRunner:
    """Выполняет Git-команды в корне проекта без использования shell."""

    def __init__(self, project_root: Path, timeout_seconds: int) -> None:
        self._project_root = project_root
        self._timeout_seconds = timeout_seconds

    def run(self, command: list[str]) -> GitCommandResultDTO:
        """Запускает Git-команду и возвращает stdout/stderr/return code."""
        completed = subprocess.run(
            command,
            cwd=self._project_root,
            capture_output=True,
            text=True,
            timeout=self._timeout_seconds,
            check=False,
        )

        return GitCommandResultDTO(
            command=shlex.join(command),
            return_code=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
