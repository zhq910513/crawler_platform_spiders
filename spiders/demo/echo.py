from __future__ import annotations

from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task

TASK_DEFINITION = {
    "definitionKey": "demo_echo",
    "taskName": "示例回显任务",
    "defaultParams": {"text": "hello"},
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
def run(context, text: str = "hello", repeat: int = 1) -> TaskResult:
    repeat = max(1, min(int(repeat), 100))
    value = text * repeat
    context.logger.info("示例任务已回显", event="demo_echo", text=text, repeat=repeat)
    return TaskResult.success("echo ok", metrics={"repeat": repeat, "length": len(value)}, data={"text": value})
