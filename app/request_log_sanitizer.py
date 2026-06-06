from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SENSITIVE_KEYS = {
    "authorization",
    "password",
    "c_password",
    "token",
    "access_token",
    "refresh_token",
    "secret_key",
}


class RequestLogSanitizer:
    """Маскирует чувствительные данные перед записью request/response логов."""

    def sanitize(self, value: Any) -> Any:
        """Рекурсивно очищает dict/list от паролей, токенов и секретов."""
        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                key_as_string = str(key)
                if key_as_string.lower() in SENSITIVE_KEYS:
                    sanitized[key_as_string] = self._mask(item)
                else:
                    sanitized[key_as_string] = self.sanitize(item)
            return sanitized

        if isinstance(value, list):
            return [self.sanitize(item) for item in value]

        return value

    def _mask(self, value: Any) -> str:
        """Заменяет чувствительное значение звёздочками, сохраняя длину строки."""
        value_as_string = "" if value is None else str(value)
        return "*" * max(len(value_as_string), 3)
