from __future__ import annotations

from collections.abc import Mapping
import html
from typing import Any


SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "password",
    "token",
    "secret",
)


class RequestLogSanitizer:
    """Маскирует чувствительные данные перед записью request/response логов."""

    def sanitize(self, value: Any) -> Any:
        """Рекурсивно очищает dict/list от паролей, токенов и секретов."""
        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                key_as_string = str(key)
                if self._is_sensitive_key(key_as_string):
                    sanitized[key_as_string] = self._mask(item)
                else:
                    sanitized[key_as_string] = self.sanitize(item)
            return sanitized

        if isinstance(value, list):
            return [self.sanitize(item) for item in value]

        return value

    def sanitize_for_frontend(self, value: Any) -> Any:
        """Маскирует секреты и HTML-экранирует строки перед отдачей логов во фронт."""
        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                key_as_string = str(key)
                frontend_key = self._escape_string(key_as_string)
                if self._is_sensitive_key(key_as_string):
                    sanitized[frontend_key] = self._mask(item)
                else:
                    sanitized[frontend_key] = self.sanitize_for_frontend(item)
            return sanitized

        if isinstance(value, list):
            return [self.sanitize_for_frontend(item) for item in value]

        if isinstance(value, str):
            return self._escape_string(value)

        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        """Определяет чувствительный ключ по фрагментам, а не только точному имени."""
        normalized = key.lower().replace("-", "_")
        return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)

    @staticmethod
    def _escape_string(value: str) -> str:
        """Экранирует строку для безопасной отдачи логов во фронт."""
        return html.escape(value, quote=True)

    def _mask(self, value: Any) -> str:
        """Заменяет чувствительное значение звёздочками, сохраняя длину строки."""
        value_as_string = "" if value is None else str(value)
        return "*" * max(len(value_as_string), 3)
