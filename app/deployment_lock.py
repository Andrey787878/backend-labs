from __future__ import annotations

import os
import time
from pathlib import Path
from uuid import uuid4


class DeploymentLockError(Exception):
    """Deployment уже выполняется другим процессом."""


class DeploymentLock:
    """Файловая блокировка deployment-процесса с TTL."""

    def __init__(self, project_root: Path, ttl_seconds: int) -> None:
        self._lock_dir = project_root / "deployment_logs"
        self._lock_file = self._lock_dir / "deploy.lock"
        self._ttl_seconds = ttl_seconds
        self._token: str | None = None
        self._lock_dir.mkdir(parents=True, exist_ok=True)

    def acquire(self) -> None:
        """Устанавливает lock или выбрасывает DeploymentLockError."""
        self._remove_stale_lock()
        token = uuid4().hex
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY

        try:
            descriptor = os.open(self._lock_file, flags, 0o600)
        except FileExistsError as exc:
            raise DeploymentLockError("Deployment already in progress") from exc

        with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
            lock_file.write(token)

        self._token = token

    def release(self) -> None:
        """Снимает lock, если он принадлежит текущему процессу."""
        if self._token is None or not self._lock_file.exists():
            return

        try:
            current_token = self._lock_file.read_text(encoding="utf-8")
        except OSError:
            return

        if current_token == self._token:
            self._lock_file.unlink(missing_ok=True)

        self._token = None

    def _remove_stale_lock(self) -> None:
        """Удаляет зависшую блокировку после истечения TTL."""
        if not self._lock_file.exists():
            return

        lock_age_seconds = time.time() - self._lock_file.stat().st_mtime
        if lock_age_seconds > self._ttl_seconds:
            self._lock_file.unlink(missing_ok=True)
