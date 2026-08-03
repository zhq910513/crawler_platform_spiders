from __future__ import annotations

import os
import signal
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from crawler_platform_spiders import APP_NAME, __version__
from crawler_platform_spiders.context import CancellationToken, TaskContext
from crawler_platform_spiders.errors import (
    ConfigurationError,
    CrawlerError,
    InfrastructureError,
    ResourceScopeMismatchError,
    TaskCancelledError,
    TaskNotFoundError,
    TaskTimeoutError,
)
from crawler_platform_spiders.io_utils import atomic_write_json, read_json
from crawler_platform_spiders.logging import ErrorSink, create_task_logger, sanitize
from crawler_platform_spiders.models import ErrorInfo, FinalResult, ResourceManifest, ResultStatus, TaskResult, TaskSpec
from crawler_platform_spiders.registry import get_task
from crawler_platform_spiders.resources import ResourceManager, SecretStore


@dataclass(frozen=True, slots=True)
class RunOptions:
    mode: str
    task_file: Path
    resources_file: Path
    secrets_file: Path
    result_file: Path
    errors_file: Path
    last_error_file: Path
    log_level: str = "INFO"
    human_logs: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_error(exc: BaseException, *, code: str | None = None, retryable: bool | None = None) -> ErrorInfo:
    if isinstance(exc, CrawlerError):
        return ErrorInfo(
            code=code or exc.code,
            type=type(exc).__name__,
            message=exc.message,
            retryable=exc.retryable if retryable is None else retryable,
            details=sanitize(exc.details),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
    return ErrorInfo(
        code=code or "RUNTIME.UNHANDLED_EXCEPTION",
        type=type(exc).__name__,
        message=str(exc) or type(exc).__name__,
        retryable=False if retryable is None else retryable,
        traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )


def _exit_code_for(status: ResultStatus, error: BaseException | None) -> int:
    if status in {ResultStatus.SUCCESS, ResultStatus.PARTIAL_SUCCESS, ResultStatus.SKIPPED}:
        return 0
    if status is ResultStatus.TIMEOUT:
        return 124
    if status is ResultStatus.CANCELLED:
        if isinstance(error, TaskCancelledError) and error.details.get("reason") == "sigterm":
            return 143
        return 130
    if isinstance(error, (ConfigurationError, ResourceScopeMismatchError, ValidationError)):
        return 2
    if isinstance(error, TaskNotFoundError):
        return 3
    if isinstance(error, InfrastructureError):
        return 4
    return 1


def _load_inputs(options: RunOptions) -> tuple[TaskSpec, ResourceManifest, SecretStore]:
    try:
        task = TaskSpec.model_validate(read_json(options.task_file), strict=True)
        resources = ResourceManifest.model_validate(read_json(options.resources_file), strict=True)
        secrets_raw = read_json(options.secrets_file)
        if not isinstance(secrets_raw, dict):
            raise ValueError("secrets file must contain a JSON object")
        secrets = SecretStore(secrets_raw)
    except (OSError, ValueError, ValidationError) as exc:
        raise ConfigurationError(
            "RUNTIME.INPUT_INVALID",
            f"Failed to load runtime input: {exc}",
            details={"task_file": str(options.task_file), "resources_file": str(options.resources_file)},
        ) from exc
    if task.company_id != resources.company_id or task.project_id != resources.project_id:
        raise ResourceScopeMismatchError(
            "RUNTIME.RESOURCE_SCOPE_MISMATCH",
            "Task and resource manifest belong to different company or project scopes",
            details={
                "task_company_id": task.company_id,
                "task_project_id": task.project_id,
                "resource_company_id": resources.company_id,
                "resource_project_id": resources.project_id,
            },
        )
    return task, resources, secrets


def _watch_timeout(token: CancellationToken, timeout_seconds: int) -> None:
    if not token.wait(timeout_seconds):
        token.cancel("timeout")


def run_task(options: RunOptions) -> int:
    started_at = _now()
    started_monotonic = time.monotonic()
    error_sink = ErrorSink(options.errors_file, options.last_error_file)
    task: TaskSpec | None = None
    resources: ResourceManager | None = None
    logger = None
    task_result: TaskResult | None = None
    terminal_error: ErrorInfo | None = None
    caught_error: BaseException | None = None
    cancellation = CancellationToken()

    previous_handlers: dict[int, Any] = {}

    try:
        task, manifest, secrets = _load_inputs(options)
        base_context = {
            "project_name": APP_NAME,
            "release_version": os.getenv("CRAWLER_RELEASE_VERSION", __version__),
            "build_sha": os.getenv("CRAWLER_BUILD_SHA", "dev"),
            "company_id": task.company_id,
            "project_id": task.project_id,
            "task_id": task.task_id,
            "run_id": task.run_id,
            "task_name": task.task_name,
            "attempt": task.attempt,
        }
        logger = create_task_logger(
            base_context=base_context,
            error_sink=error_sink,
            level=options.log_level,
            human_logs=options.human_logs,
        )

        def handle_signal(signum: int, _frame: Any) -> None:
            reason = "sigterm" if signum == signal.SIGTERM else "sigint"
            cancellation.cancel(reason)
            logger.warning("Cancellation signal received", event="cancellation_requested", signal=signum)

        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, handle_signal)

        definition = get_task(task.task_name)
        parameters = (
            definition.parameter_model.model_validate(task.parameters, strict=True)
            if definition.parameter_model
            else task.parameters
        )
        resources = ResourceManager(manifest, secrets)
        resources.validate_required(definition.required_resources)
        context = TaskContext(task, parameters, logger, resources, secrets, cancellation)

        timeout_thread = threading.Thread(
            target=_watch_timeout,
            args=(cancellation, task.timeout_seconds),
            daemon=True,
            name="task-timeout-watchdog",
        )
        timeout_thread.start()

        logger.info(
            "Task started",
            event="task_started",
            image_profile=definition.image_profile,
            timeout_seconds=task.timeout_seconds,
        )
        task_result = definition.entrypoint(context)
        if not isinstance(task_result, TaskResult):
            raise ConfigurationError(
                "RUNTIME.INVALID_TASK_RESULT",
                "Spider entrypoint must return TaskResult",
                details={"returned_type": type(task_result).__name__},
            )
        if cancellation.is_cancelled():
            cancellation.raise_if_cancelled()

    except TaskTimeoutError as exc:
        caught_error = exc
        terminal_error = _build_error(exc)
        if logger:
            logger.error(
                exc.message,
                event="task_timeout",
                error_code=exc.code,
                retryable=exc.retryable,
                exc=exc,
                **exc.details,
            )
        task_result = TaskResult(status=ResultStatus.TIMEOUT, message=exc.message, error=terminal_error)
    except TaskCancelledError as exc:
        caught_error = exc
        terminal_error = _build_error(exc)
        if logger:
            logger.warning(exc.message, event="task_cancelled", **exc.details)
        task_result = TaskResult(status=ResultStatus.CANCELLED, message=exc.message, error=terminal_error)
    except BaseException as exc:
        caught_error = exc
        terminal_error = _build_error(exc)
        if logger:
            logger.error(
                terminal_error.message,
                event="task_failed",
                error_code=terminal_error.code,
                retryable=terminal_error.retryable,
                exc=exc,
                **terminal_error.details,
            )
        else:
            sys.stderr.write(f"TASK_BOOTSTRAP_FAILURE {type(exc).__name__}: {exc}\n")
            sys.stderr.flush()
        task_result = TaskResult.failed(terminal_error.message, error=terminal_error)
    finally:
        if resources is not None:
            close_errors = resources.close()
            if logger:
                for close_error in close_errors:
                    logger.warning(
                        "Resource close failed",
                        event="resource_close_failed",
                        resource_error_type=type(close_error).__name__,
                        resource_error=str(close_error),
                    )
        for signum, previous in previous_handlers.items():
            try:
                signal.signal(signum, previous)
            except BaseException:
                pass

    finished_at = _now()
    task_result = task_result or TaskResult.failed("Task did not produce a result")
    if task_result.error and terminal_error is None and task_result.status in {
        ResultStatus.FAILED,
        ResultStatus.CANCELLED,
        ResultStatus.TIMEOUT,
    }:
        terminal_error = task_result.error
    exit_code = _exit_code_for(task_result.status, caught_error)

    if task is None:
        # 输入文件本身无效时仍尽最大可能写出结构化结果。
        fallback = {
            "schema_version": "1.0",
            "project_name": APP_NAME,
            "release_version": os.getenv("CRAWLER_RELEASE_VERSION", __version__),
            "build_sha": os.getenv("CRAWLER_BUILD_SHA", "dev"),
            "image_digest": os.getenv("CRAWLER_IMAGE_DIGEST") or None,
            "status": task_result.status.value,
            "exit_code": exit_code,
            "message": task_result.message,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
            "last_error": error_sink.last_error.model_dump(mode="json") if error_sink.last_error else None,
            "terminal_error": terminal_error.model_dump(mode="json") if terminal_error else None,
        }
        try:
            atomic_write_json(options.result_file, fallback)
        except BaseException as exc:
            sys.stderr.write(f"RESULT_WRITE_FAILURE {type(exc).__name__}: {exc}\n")
        return exit_code

    final_result = FinalResult(
        release_version=os.getenv("CRAWLER_RELEASE_VERSION", __version__),
        build_sha=os.getenv("CRAWLER_BUILD_SHA", "dev"),
        image_digest=os.getenv("CRAWLER_IMAGE_DIGEST") or None,
        company_id=task.company_id,
        project_id=task.project_id,
        task_id=task.task_id,
        run_id=task.run_id,
        task_name=task.task_name,
        attempt=task.attempt,
        status=task_result.status,
        exit_code=exit_code,
        message=task_result.message,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=int((time.monotonic() - started_monotonic) * 1000),
        metrics=task_result.metrics,
        last_error=error_sink.last_error,
        terminal_error=terminal_error,
    )
    try:
        atomic_write_json(options.result_file, final_result.model_dump(mode="json"))
    except BaseException as exc:
        sys.stderr.write(f"RESULT_WRITE_FAILURE {type(exc).__name__}: {exc}\n")
        sys.stderr.flush()
        return 1

    if logger:
        logger.info(
            "Task finished",
            event="task_finished",
            status=task_result.status.value,
            exit_code=exit_code,
            duration_ms=final_result.duration_ms,
        )
    return exit_code
