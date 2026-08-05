from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["success", "partial_success", "skipped", "failed"]


@dataclass(slots=True)
class TaskResult:
    status: Status
    message: str
    metrics: dict[str, int | float | str | bool | None] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None

    @classmethod
    def success(cls, message: str = "success", *, metrics: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> "TaskResult":
        return cls("success", message, metrics or {}, data or {})

    @classmethod
    def partial_success(cls, message: str, *, metrics: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> "TaskResult":
        return cls("partial_success", message, metrics or {}, data or {})

    @classmethod
    def skipped(cls, message: str, *, metrics: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> "TaskResult":
        return cls("skipped", message, metrics or {}, data or {})

    @classmethod
    def failed(cls, message: str, *, error: dict[str, Any] | None = None, metrics: dict[str, Any] | None = None) -> "TaskResult":
        return cls("failed", message, metrics or {}, {}, error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "metrics": self.metrics,
            "data": self.data,
            "error": self.error,
        }
