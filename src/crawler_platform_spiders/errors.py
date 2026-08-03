from __future__ import annotations

from typing import Any


class CrawlerError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


class ConfigurationError(CrawlerError):
    pass


class TaskNotFoundError(CrawlerError):
    pass


class ResourceScopeMismatchError(CrawlerError):
    pass


class InfrastructureError(CrawlerError):
    pass


class AuthenticationError(CrawlerError):
    pass


class TaskCancelledError(CrawlerError):
    pass


class TaskTimeoutError(CrawlerError):
    pass
