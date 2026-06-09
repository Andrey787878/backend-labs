from __future__ import annotations

from pathlib import Path

from app.deployment_lock import DeploymentLock, DeploymentLockError
from app.deployment_logger import DeploymentLogger
from app.dto import DeploymentResponseDTO, GitCommandResultDTO
from app.git_command_runner import GitCommandRunner


class DeploymentServiceError(Exception):
    """Базовое исключение deployment-сервиса."""


class DeploymentRepositoryError(DeploymentServiceError):
    """Текущая директория не является Git-репозиторием."""


class DeploymentCommandError(DeploymentServiceError):
    """Git-команда завершилась с ошибкой."""

    def __init__(self, result: GitCommandResultDTO) -> None:
        self.result = result
        super().__init__(f"Git command failed: {result.command}")


class DeploymentService:
    """Выполняет синхронное обновление проекта через Git webhook."""

    def __init__(
        self,
        project_root: Path,
        branch: str,
        lock_ttl_seconds: int,
        command_timeout_seconds: int,
    ) -> None:
        self._project_root = project_root
        self._branch = branch
        self._logger = DeploymentLogger(project_root=project_root)
        self._lock = DeploymentLock(project_root=project_root, ttl_seconds=lock_ttl_seconds)
        self._runner = GitCommandRunner(
            project_root=project_root,
            timeout_seconds=command_timeout_seconds,
        )

    def deploy(self, client_ip: str | None) -> DeploymentResponseDTO:
        """Запускает deployment-процесс и возвращает JSON-ready DTO."""
        self._logger.log_start(client_ip=client_ip)

        commands: list[GitCommandResultDTO] = []
        warnings: list[str] = []
        lock_acquired = False

        try:
            self._lock.acquire()
            lock_acquired = True
            self._ensure_git_repository()
            warnings.extend(self._prepare_worktree())

            for command in self._build_commands():
                self._run_git_command(command=command, commands=commands)

            message = "Deployment completed successfully"
            self._logger.log_finish(status="success", message=message)
            return DeploymentResponseDTO(
                message=message,
                branch=self._branch,
                warnings=warnings,
                commands=commands,
            )
        except DeploymentLockError:
            self._logger.log_finish(status="conflict", message="Deployment already in progress")
            raise
        except Exception as exc:
            self._logger.log(
                "deployment_error",
                status="failed",
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
            self._logger.log_finish(status="failed", message="Deployment failed")
            raise
        finally:
            if lock_acquired:
                self._lock.release()

    def _ensure_git_repository(self) -> None:
        """Проверяет, что deployment запускается из корня Git-репозитория."""
        if not (self._project_root / ".git").exists():
            raise DeploymentRepositoryError("Current project root is not a Git repository")

    def _prepare_worktree(self) -> list[str]:
        """Фиксирует и очищает локальные изменения, чтобы deployment не блокировался."""
        status_result = self._run_git_command(
            command=["git", "status", "--porcelain", "--untracked-files=all"],
            commands=None,
            event="git_preflight_command",
        )
        dirty_files = [
            line
            for line in status_result.stdout.splitlines()
            if line.strip() and not _is_deployment_artifact_status_line(line)
        ]
        if not dirty_files:
            return []

        warning = (
            "Dirty worktree detected and discarded before deployment. "
            "See deployment_logs/deployment.log for affected files."
        )
        self._logger.log(
            "dirty_worktree_detected",
            status="warning",
            files=dirty_files,
            files_count=len(dirty_files),
        )

        self._run_git_command(
            command=["git", "reset", "--hard", "HEAD"],
            commands=None,
            event="git_preflight_command",
        )
        self._run_git_command(
            command=["git", "clean", "-fd", "-e", "deployment_logs/"],
            commands=None,
            event="git_preflight_command",
        )
        self._logger.log(
            "dirty_worktree_discarded",
            status="warning",
            files_count=len(dirty_files),
        )
        return [warning]

    def _run_git_command(
        self,
        command: list[str],
        commands: list[GitCommandResultDTO] | None,
        event: str = "git_command",
    ) -> GitCommandResultDTO:
        """Выполняет Git-команду, логирует результат и проверяет код завершения."""
        result = self._runner.run(command)
        if commands is not None:
            commands.append(result)
        self._logger.log(
            event,
            status="success" if result.return_code == 0 else "failed",
            command=result.command,
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        if result.return_code != 0:
            raise DeploymentCommandError(result)
        return result

    def _build_commands(self) -> list[list[str]]:
        """Возвращает Git-команды в обязательной для лабораторной последовательности."""
        return [
            ["git", "checkout", self._branch],
            ["git", "reset", "--hard", "HEAD"],
            ["git", "pull", "origin", self._branch],
        ]


def _is_deployment_artifact_status_line(line: str) -> bool:
    """Исключает собственные runtime-артефакты webhook-а из dirty warning."""
    normalized = line.strip()
    if not normalized.startswith("?? "):
        return False

    path = normalized[3:]
    return path == "deployment_logs" or path.startswith("deployment_logs/")
