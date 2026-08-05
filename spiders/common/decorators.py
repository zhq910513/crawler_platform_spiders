from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from crawler_foundation.core.context import TaskContext
from crawler_foundation.core.exceptions import CrawlerError
from crawler_foundation.core.result import TaskResult

F = TypeVar("F", bound=Callable[..., Any])

_PLATFORM_META_KEYS = {
    "runId", "run_id", "companyId", "company_id", "projectId", "project_id", "projectCode", "project_code",
    "taskId", "task_id", "taskCode", "task_code", "taskGroup", "task_group", "shardIndex", "shard_index",
    "shardCount", "shard_count",
}


def _build_context_and_kwargs(kwargs: dict[str, Any]) -> tuple[TaskContext, dict[str, Any]]:
    context = TaskContext.from_env(kwargs)
    business_kwargs = {k: v for k, v in kwargs.items() if k not in _PLATFORM_META_KEYS}
    return context, business_kwargs


def _success_from_value(value: Any) -> dict[str, Any]:
    result = value if isinstance(value, TaskResult) else TaskResult.success("success", data={"value": value})
    return result.to_dict()


def _failure_from_error(context: TaskContext, exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, CrawlerError):
        error = context.logger.error(
            exc.message,
            event="task_failed",
            exc=exc,
            error_code=exc.code,
            retryable=exc.retryable,
            **exc.details,
        )
        error["exitCode"] = exc.exit_code
        return TaskResult.failed(exc.message, error=error).to_dict()
    error = context.logger.error(
        str(exc) or type(exc).__name__,
        event="task_failed",
        exc=exc,
        error_code="SPIDER.UNHANDLED_EXCEPTION",
        retryable=False,
    )
    error["exitCode"] = 90
    return TaskResult.failed(str(exc) or type(exc).__name__, error=error).to_dict()


def platform_task() -> Callable[[F], Callable[..., Any]]:
    def decorator(func: F) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
                context, business_kwargs = _build_context_and_kwargs(kwargs)
                context.logger.info("任务开始", event="task_started", parameters=kwargs)
                try:
                    value = await func(context, *args, **business_kwargs)
                    result = _success_from_value(value)
                    context.logger.info("任务完成", event="task_finished", status=result.get("status"), metrics=result.get("metrics"))
                    return result
                except BaseException as exc:
                    return _failure_from_error(context, exc)

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            context, business_kwargs = _build_context_and_kwargs(kwargs)
            context.logger.info("任务开始", event="task_started", parameters=kwargs)
            try:
                value = func(context, *args, **business_kwargs)
                result = _success_from_value(value)
                context.logger.info("任务完成", event="task_finished", status=result.get("status"), metrics=result.get("metrics"))
                return result
            except BaseException as exc:
                return _failure_from_error(context, exc)

        return wrapper

    return decorator
