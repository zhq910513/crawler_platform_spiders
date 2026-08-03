from __future__ import annotations

import inspect
import json
import logging
import os
import re
import sys
import threading
import traceback as traceback_module
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crawler_platform_spiders.io_utils import atomic_write_json
from crawler_platform_spiders.models import ErrorInfo

_SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|pwd|secret|token|cookie|authorization|access[_-]?key|private[_-]?key|uri)$",
    re.IGNORECASE,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


class ErrorSink:
    def __init__(self, errors_file: str | Path, last_error_file: str | Path) -> None:
        self.errors_file = Path(errors_file)
        self.last_error_file = Path(last_error_file)
        self.errors_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_error_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_error: ErrorInfo | None = None

    @property
    def last_error(self) -> ErrorInfo | None:
        with self._lock:
            return self._last_error.model_copy(deep=True) if self._last_error else None

    def record(self, event: dict[str, Any], error: ErrorInfo) -> None:
        safe_event = sanitize(event)
        try:
            with self._lock:
                with self.errors_file.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(safe_event, ensure_ascii=False, separators=(",", ":"), default=str))
                    file.write("\n")
                    file.flush()
                    os.fsync(file.fileno())
                atomic_write_json(self.last_error_file, error.model_dump(mode="json"))
                self._last_error = error
        except BaseException as exc:
            sys.stderr.write(f"ERROR_SINK_FAILURE {type(exc).__name__}: {exc}\n")
            sys.stderr.flush()


class EventJsonFormatter(logging.Formatter):
    def __init__(self, base_context: dict[str, Any]) -> None:
        super().__init__()
        self.base_context = base_context

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "crawler_event", None)
        if event is None:
            event = {
                "schema": "crawler.event.v1",
                "event_id": f"evt_{uuid.uuid4().hex}",
                "timestamp": utc_now().isoformat().replace("+00:00", "Z"),
                "level": record.levelname,
                "event": "library_log",
                "message": record.getMessage(),
                **self.base_context,
                "logger": record.name,
            }
            if record.exc_info:
                event["traceback"] = self.formatException(record.exc_info)
        elif "source" not in event:
            event["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }
        return json.dumps(sanitize(event), ensure_ascii=False, separators=(",", ":"), default=str)


class HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "crawler_event", None)
        if event:
            timestamp = event.get("timestamp", "")
            level = event.get("level", record.levelname)
            name = event.get("event", "log")
            message = event.get("message", record.getMessage())
            return f"{timestamp} | {level:<8} | {name} | {message}"
        return f"{record.levelname:<8} | {record.name} | {record.getMessage()}"


def configure_root_logging(level: str, base_context: dict[str, Any], human_logs: bool) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(HumanFormatter() if human_logs else EventJsonFormatter(base_context))
    root.addHandler(handler)


class TaskLogger:
    def __init__(
        self,
        logger: logging.Logger,
        base_context: dict[str, Any],
        error_sink: ErrorSink,
        bound_fields: dict[str, Any] | None = None,
    ) -> None:
        self._logger = logger
        self._base_context = base_context
        self._error_sink = error_sink
        self._bound_fields = bound_fields or {}

    def bind(self, **fields: Any) -> "TaskLogger":
        merged = {**self._bound_fields, **sanitize(fields)}
        return TaskLogger(self._logger, self._base_context, self._error_sink, merged)

    def debug(self, message: str, *, event: str = "debug", **fields: Any) -> None:
        self._emit(logging.DEBUG, message, event=event, fields=fields)

    def info(self, message: str, *, event: str = "info", **fields: Any) -> None:
        self._emit(logging.INFO, message, event=event, fields=fields)

    def warning(self, message: str, *, event: str = "warning", **fields: Any) -> None:
        self._emit(logging.WARNING, message, event=event, fields=fields)

    def error(
        self,
        message: str,
        *,
        event: str = "error",
        error_code: str = "SPIDER.ERROR",
        retryable: bool = False,
        exc: BaseException | None = None,
        **fields: Any,
    ) -> ErrorInfo:
        return self._emit_error(
            logging.ERROR,
            message,
            event=event,
            error_code=error_code,
            retryable=retryable,
            exc=exc,
            fields=fields,
        )

    def exception(
        self,
        message: str,
        *,
        event: str = "exception",
        error_code: str = "SPIDER.EXCEPTION",
        retryable: bool = False,
        exc: BaseException | None = None,
        **fields: Any,
    ) -> ErrorInfo:
        actual_exc = exc or sys.exc_info()[1]
        return self._emit_error(
            logging.ERROR,
            message,
            event=event,
            error_code=error_code,
            retryable=retryable,
            exc=actual_exc,
            fields=fields,
        )

    def critical(
        self,
        message: str,
        *,
        event: str = "critical",
        error_code: str = "SPIDER.CRITICAL",
        retryable: bool = False,
        exc: BaseException | None = None,
        **fields: Any,
    ) -> ErrorInfo:
        return self._emit_error(
            logging.CRITICAL,
            message,
            event=event,
            error_code=error_code,
            retryable=retryable,
            exc=exc,
            fields=fields,
        )

    def _event(self, level: str, message: str, event: str, fields: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": "crawler.event.v1",
            "event_id": f"evt_{uuid.uuid4().hex}",
            "timestamp": utc_now().isoformat().replace("+00:00", "Z"),
            "level": level,
            "event": event,
            "message": message,
            **self._base_context,
            "context": sanitize({**self._bound_fields, **fields}),
        }

    def _emit(self, level: int, message: str, *, event: str, fields: dict[str, Any]) -> None:
        payload = self._event(logging.getLevelName(level), message, event, fields)
        self._logger.log(level, message, extra={"crawler_event": payload}, stacklevel=3)

    @staticmethod
    def _caller_source() -> dict[str, Any] | None:
        frame = inspect.currentframe()
        try:
            for _ in range(3):
                if frame is None:
                    return None
                frame = frame.f_back
            if frame is None:
                return None
            return {
                "file": frame.f_code.co_filename,
                "line": frame.f_lineno,
                "function": frame.f_code.co_name,
            }
        finally:
            del frame

    def _emit_error(
        self,
        level: int,
        message: str,
        *,
        event: str,
        error_code: str,
        retryable: bool,
        exc: BaseException | None,
        fields: dict[str, Any],
    ) -> ErrorInfo:
        trace = None
        error_type = type(exc).__name__ if exc else "SpiderError"
        if exc:
            trace = "".join(traceback_module.format_exception(type(exc), exc, exc.__traceback__))
        error = ErrorInfo(
            code=error_code,
            type=error_type,
            message=message,
            retryable=retryable,
            details=sanitize({**self._bound_fields, **fields}),
            traceback=trace,
        )
        payload = self._event(logging.getLevelName(level), message, event, fields)
        source = self._caller_source()
        if source:
            payload["source"] = source
        payload["error"] = error.model_dump(mode="json")
        self._error_sink.record(payload, error)
        self._logger.log(level, message, extra={"crawler_event": payload}, stacklevel=3)
        return error


def create_task_logger(
    *,
    base_context: dict[str, Any],
    error_sink: ErrorSink,
    level: str = "INFO",
    human_logs: bool = False,
) -> TaskLogger:
    configure_root_logging(level, base_context, human_logs)
    logger = logging.getLogger("crawler_platform_spiders.task")
    logger.handlers.clear()
    logger.setLevel(level.upper())
    logger.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(HumanFormatter() if human_logs else EventJsonFormatter(base_context))
    logger.addHandler(handler)
    return TaskLogger(logger, deepcopy(base_context), error_sink)
