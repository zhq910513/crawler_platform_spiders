from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from crawler_platform_spiders.errors import ConfigurationError, TaskNotFoundError
from crawler_platform_spiders.models import TaskResult

TaskEntrypoint = Callable[[Any], TaskResult]


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    name: str
    entrypoint: TaskEntrypoint
    description: str
    image_profile: Literal["api", "browser"] = "api"
    default_timeout_seconds: int = 3600
    parameter_model: type[BaseModel] | None = None
    required_resources: tuple[str, ...] = ()

    def parameter_schema(self) -> dict[str, Any]:
        return self.parameter_model.model_json_schema() if self.parameter_model else {"type": "object"}


_TASKS: dict[str, TaskDefinition] = {}
_BUILTINS_LOADED = False


def register_task(definition: TaskDefinition) -> None:
    if definition.name in _TASKS:
        raise ConfigurationError(
            "RUNTIME.DUPLICATE_TASK",
            f"Task is already registered: {definition.name}",
        )
    _TASKS[definition.name] = definition


def task(
    name: str,
    *,
    description: str,
    image_profile: Literal["api", "browser"] = "api",
    default_timeout_seconds: int = 3600,
    parameter_model: type[BaseModel] | None = None,
    required_resources: tuple[str, ...] = (),
):
    def decorator(entrypoint: TaskEntrypoint) -> TaskEntrypoint:
        register_task(
            TaskDefinition(
                name=name,
                entrypoint=entrypoint,
                description=description,
                image_profile=image_profile,
                default_timeout_seconds=default_timeout_seconds,
                parameter_model=parameter_model,
                required_resources=required_resources,
            )
        )
        return entrypoint

    return decorator


def load_builtin_tasks() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    # 新增爬虫平台时，在此处显式导入其任务模块。禁止从 TaskSpec 动态导入任意 Python 路径。
    from crawler_platform_spiders.spiders.system import health  # noqa: F401

    _BUILTINS_LOADED = True


def get_task(name: str) -> TaskDefinition:
    load_builtin_tasks()
    definition = _TASKS.get(name)
    if definition is None:
        raise TaskNotFoundError(
            "RUNTIME.TASK_NOT_FOUND",
            f"Task is not registered: {name}",
            details={"task_name": name},
        )
    return definition


def list_tasks() -> list[TaskDefinition]:
    load_builtin_tasks()
    return sorted(_TASKS.values(), key=lambda item: item.name)
