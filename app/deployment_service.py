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
        lock_acquired = False

        try:
            self._lock.acquire()
            lock_acquired = True
            self._ensure_git_repository()

            for command in self._build_commands():
                result = self._runner.run(command)
                commands.append(result)
                self._logger.log(
                    "git_command",
                    status="success" if result.return_code == 0 else "failed",
                    command=result.command,
                    return_code=result.return_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                if result.return_code != 0:
                    raise DeploymentCommandError(result)

            message = "Deployment completed successfully"
            self._logger.log_finish(status="success", message=message)
            return DeploymentResponseDTO(message=message, branch=self._branch, commands=commands)
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

    def _build_commands(self) -> list[list[str]]:
        """Возвращает Git-команды в обязательной для лабораторной последовательности."""
        return [
            ["git", "checkout", self._branch],
            ["git", "reset", "--hard", "HEAD"],
            ["git", "pull", "origin", self._branch],
        ]
