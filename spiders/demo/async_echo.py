from __future__ import annotations

import asyncio

from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task

TASK_DEFINITION = {
    "definitionKey": "demo_async_echo",
    "taskName": "示例异步回显任务",
    "defaultParams": {"text": "async"},
    "suggestedCron": "",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "resourceRequirements": {},
    "requiredCapabilities": {"browser": False},
    "runtimeMode": "SHARED_ENV_ISOLATED",
    "taskGroup": "demo",
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
async def run(context, text: str = "async", delay_seconds: float = 0.0) -> TaskResult:
    if delay_seconds:
        await asyncio.sleep(float(delay_seconds))
    context.logger.info("异步示例任务已回显", event="demo_async_echo", text=text)
    return TaskResult.success("async echo ok", data={"text": text})
