from __future__ import annotations

from crawler_foundation.core.exceptions import LoginError
from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task

TASK_DEFINITION = {
    "definitionKey": "system_health",
    "taskName": "系统健康检查",
    "defaultParams": {"message": "health check passed"},
    "suggestedCron": "",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "resourceRequirements": {},
    "requiredCapabilities": {"browser": False},
    "runtimeMode": "SHARED_ENV_ISOLATED",
    "taskGroup": "system",
    "taskMaxConcurrency": 1,
    "groupMaxConcurrency": 4,
    "exclusiveMode": False,
    "ioClass": "LOW",
    "shmSizeMb": 64,
    "logLimitMb": 20,
    "resourceLocks": [],
    "secretRefs": [],
}


@platform_task()
def run(context, message: str = "health check passed", sleep_seconds: float = 0.0, raise_login_error: bool = False) -> TaskResult:
    context.logger.info("健康检查开始", event="health_started")
    if sleep_seconds:
        import time

        time.sleep(float(sleep_seconds))
    if raise_login_error:
        raise LoginError("模拟登录失败", code="SYSTEM.LOGIN_FAILED", retryable=False)
    context.logger.info(message, event="health_completed")
    return TaskResult.success(message, metrics={"healthy": True})
