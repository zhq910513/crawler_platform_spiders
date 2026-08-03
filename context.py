from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from crawler_platform_spiders.errors import TaskCancelledError, TaskTimeoutError
from crawler_platform_spiders.logging import TaskLogger
from crawler_platform_spiders.models import TaskSpec
from crawler_platform_spiders.resources import ResourceManager, SecretStore

TModel = TypeVar("TModel", bound=BaseModel)


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._reason: str | None = None

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    def cancel(self, reason: str) -> None:
        with self._lock:
            if self._reason is None:
                self._reason = reason
                self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, seconds: float) -> bool:
        return self._event.wait(seconds)

    def raise_if_cancelled(self) -> None:
        if not self.is_cancelled():
            return
        reason = self.reason or "cancelled"
        if reason == "timeout":
            raise TaskTimeoutError("RUNTIME.TIMEOUT", "Task timeout reached", retryable=True)
        raise TaskCancelledError(
            "RUNTIME.CANCELLED",
            "Task cancellation requested",
            retryable=False,
            details={"reason": reason},
        )


@dataclass(slots=True)
class TaskContext:
    task: TaskSpec
    parameters: BaseModel | dict[str, Any]
    logger: TaskLogger
    resources: ResourceManager
    secrets: SecretStore
    cancellation: CancellationToken

    @property
    def mysql(self):
        return self.resources.mysql

    @property
    def mongo(self):
        return self.resources.mongo

    @property
    def redis(self):
        return self.resources.redis

    @property
    def http(self):
        return self.resources.http

    def parameters_as(self, model: type[TModel]) -> TModel:
        if isinstance(self.parameters, model):
            return self.parameters
        raw = self.parameters.model_dump() if isinstance(self.parameters, BaseModel) else self.parameters
        return model.model_validate(raw, strict=True)

    def is_cancelled(self) -> bool:
        return self.cancellation.is_cancelled()

    def raise_if_cancelled(self) -> None:
        self.cancellation.raise_if_cancelled()

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        if self.cancellation.wait(seconds):
            self.cancellation.raise_if_cancelled()
