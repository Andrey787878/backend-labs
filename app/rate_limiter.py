"""Назначение: in-memory rate-limit для auth-эндпоинтов."""

from __future__ import annotations

from collections import OrderedDict, deque
from threading import Lock
from time import monotonic


class InMemorySlidingWindowRateLimiter:
    """Ограничивает число запросов на ключ в скользящем временном окне."""

    def __init__(
        self,
        max_tracked_keys: int = 50_000,
        cleanup_interval_seconds: int = 30,
    ) -> None:
        """Инициализирует in-memory хранилище со сборкой устаревших ключей."""
        if max_tracked_keys <= 0:
            raise ValueError("max_tracked_keys должен быть положительным.")
        if cleanup_interval_seconds <= 0:
            raise ValueError("cleanup_interval_seconds должен быть положительным.")

        # Храним ключи в OrderedDict, чтобы при переполнении удалять самые старые.
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        # Для корректной очистки у каждого ключа запоминаем его текущее окно лимита.
        self._windows: dict[str, float] = {}
        self._max_tracked_keys = max_tracked_keys
        self._cleanup_interval_seconds = float(cleanup_interval_seconds)
        self._last_cleanup_at = 0.0
        self._lock = Lock()

    def _maybe_cleanup(self, now: float) -> None:
        """Периодически удаляет ключи, у которых окно лимита полностью истекло."""
        if now - self._last_cleanup_at < self._cleanup_interval_seconds:
            return

        for stored_key, bucket in list(self._requests.items()):
            window = self._windows.get(stored_key)
            if window is None:
                self._requests.pop(stored_key, None)
                continue

            cutoff = now - window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if not bucket:
                self._requests.pop(stored_key, None)
                self._windows.pop(stored_key, None)

        self._last_cleanup_at = now

    def _evict_if_needed(self, exclude_key: str) -> None:
        """Ограничивает число отслеживаемых ключей и вытесняет самые старые."""
        while len(self._requests) > self._max_tracked_keys:
            oldest_key = next(iter(self._requests))
            if oldest_key == exclude_key:
                self._requests.move_to_end(oldest_key)
                if len(self._requests) == 1:
                    break
                oldest_key = next(iter(self._requests))

            self._requests.pop(oldest_key, None)
            self._windows.pop(oldest_key, None)

    def allow(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, float]:
        """Проверяет лимит и возвращает флаг допуска и retry-after в секундах."""
        if max_requests <= 0:
            raise ValueError("max_requests должен быть положительным.")
        if window_seconds <= 0:
            raise ValueError("window_seconds должен быть положительным.")

        now = monotonic()
        window = float(window_seconds)
        cutoff = now - window

        with self._lock:
            self._maybe_cleanup(now=now)
            bucket = self._requests.get(key)
            if bucket is None:
                bucket = deque()
                self._requests[key] = bucket
            else:
                self._requests.move_to_end(key)

            self._windows[key] = window

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= max_requests:
                retry_after = window - (now - bucket[0])
                return False, max(retry_after, 0.0)

            bucket.append(now)
            self._requests.move_to_end(key)
            self._evict_if_needed(exclude_key=key)
            return True, 0.0
