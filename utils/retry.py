"""Retry, health-check, and graceful-degradation utilities."""

import time
import logging
import functools
from datetime import datetime, timezone

logger = logging.getLogger("utils.retry")


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """Decorator: retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds between retries.
        max_delay: Cap on the delay between retries.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        break
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                        func.__name__, attempt + 1, max_retries + 1, exc, delay,
                    )
                    time.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def graceful_degrade(fallback_value=None):
    """Decorator: catch exceptions and return a fallback instead of crashing.

    Logs the failure so operators know the feature is running in degraded mode.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.error(
                    "%s failed (degraded mode): %s — returning fallback",
                    func.__name__, exc,
                )
                return fallback_value
        return wrapper
    return decorator


class ServiceHealthChecker:
    """Tracks availability of external services."""

    def __init__(self):
        self._status: dict[str, dict] = {}

    def record_success(self, service: str):
        self._status[service] = {
            "healthy": True,
            "last_check": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
        }

    def record_failure(self, service: str, error: str):
        self._status[service] = {
            "healthy": False,
            "last_check": datetime.now(timezone.utc).isoformat(),
            "last_error": error,
        }

    def is_healthy(self, service: str) -> bool:
        entry = self._status.get(service)
        return entry["healthy"] if entry else False

    def get_status(self) -> dict[str, dict]:
        return dict(self._status)

    def summary(self) -> str:
        if not self._status:
            return "No services checked yet."
        lines = []
        for svc, info in self._status.items():
            icon = "OK" if info["healthy"] else "DOWN"
            lines.append(f"  {svc}: {icon} (checked {info['last_check']})")
        return "\n".join(lines)


# Module-level singleton so all modules share one checker.
health = ServiceHealthChecker()
