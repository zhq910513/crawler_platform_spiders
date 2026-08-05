from __future__ import annotations

import json
import logging
import os
import re
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

from crawler_foundation.core.files import atomic_write_json
from crawler_foundation.core.time_utils import utc_iso

_SENSITIVE_KEY = re.compile(r"(?:password|passwd|pwd|secret|token|cookie|authorization|access[_-]?key|private[_-]?key|uri)$", re.I)


def sanitize(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    if key and _SENSITIVE_KEY.search(key):
        return "***REDACTED***"
    if depth > 8:
        return "<max-depth>"
    if isinstance(value, dict):
        return {str(k): sanitize(v, key=str(k), depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize(item, depth=depth + 1) for item in value]
    if isinstance(value, BaseException):
        return f"{type(value).__name__}: {value}"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    def __init__(self, base_context: dict[str, Any]) -> None:
        super().__init__()
        self.base_context = base_context

    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "crawler_event", None)
        if payload is None:
            payload = {
                "schema": "crawler.event.v1",
                "eventId": f"evt_{uuid.uuid4().hex}",
                "timestamp": utc_iso(),
                "level": record.levelname,
                "event": "library_log",
                "message": record.getMessage(),
                **self.base_context,
                "logger": record.name,
            }
            if record.exc_info:
                payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(sanitize(payload), ensure_ascii=False, separators=(",", ":"), default=str)


class HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "crawler_event", None)
        if payload:
            return f"{payload.get('timestamp')} | {payload.get('level')} | {payload.get('event')} | {payload.get('message')}"
        return f"{record.levelname} | {record.name} | {record.getMessage()}"


class TaskLogger:
    def __init__(self, logger: logging.Logger, base_context: dict[str, Any], *, last_error_file: Path | None = None, bound: dict[str, Any] | None = None) -> None:
        self._logger = logger
        self._base_context = base_context
        self._last_error_file = last_error_file
        self._bound = bound or {}

    def bind(self, **fields: Any) -> "TaskLogger":
        return TaskLogger(self._logger, self._base_context, last_error_file=self._last_error_file, bound={**self._bound, **sanitize(fields)})

    def debug(self, message: str, *, event: str = "debug", **fields: Any) -> None:
        self._emit(logging.DEBUG, message, event, fields)

    def info(self, message: str, *, event: str = "info", **fields: Any) -> None:
        self._emit(logging.INFO, message, event, fields)

    def warning(self, message: str, *, event: str = "warning", **fields: Any) -> None:
        self._emit(logging.WARNING, message, event, fields)

    def error(self, message: str, *, event: str = "error", exc: BaseException | None = None, error_code: str = "SPIDER.ERROR", retryable: bool = False, **fields: Any) -> dict[str, Any]:
        error = {
            "code": error_code,
            "type": type(exc).__name__ if exc else "SpiderError",
            "message": message,
            "retryable": retryable,
            "details": sanitize(fields),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else None,
        }
        self._emit(logging.ERROR, message, event, {**fields, "error": error})
        if self._last_error_file:
            atomic_write_json(self._last_error_file, error)
        return error

    def exception(self, message: str, *, event: str = "exception", error_code: str = "SPIDER.EXCEPTION", retryable: bool = False, **fields: Any) -> dict[str, Any]:
        exc = sys.exc_info()[1]
        return self.error(message, event=event, exc=exc, error_code=error_code, retryable=retryable, **fields)

    def _emit(self, level: int, message: str, event: str, fields: dict[str, Any]) -> None:
        payload = {
            "schema": "crawler.event.v1",
            "eventId": f"evt_{uuid.uuid4().hex}",
            "timestamp": utc_iso(),
            "level": logging.getLevelName(level),
            "event": event,
            "message": message,
            **self._base_context,
            "context": sanitize({**self._bound, **fields}),
        }
        self._logger.log(level, message, extra={"crawler_event": payload}, stacklevel=3)


def create_logger(*, name: str = "crawler_platform_spiders", level: str | None = None, base_context: dict[str, Any] | None = None, human: bool | None = None, last_error_file: str | Path | None = None) -> TaskLogger:
    actual_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    actual_human = bool(human) or os.getenv("HUMAN_LOGS") == "1"
    base = base_context or {}
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(actual_level)
    logger.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(HumanFormatter() if actual_human else JsonFormatter(base))
    logger.addHandler(handler)
    return TaskLogger(logger, base, last_error_file=Path(last_error_file) if last_error_file else None)
