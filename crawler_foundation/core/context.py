from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crawler_foundation import __version__
from crawler_foundation.core.files import ensure_dir
from crawler_foundation.core.json_utils import loads_dict, loads_list
from crawler_foundation.core.logging import TaskLogger, create_logger


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value or ""
    return default


def _safe_int(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class RuntimeDirs:
    work: Path
    logs: Path
    cache: Path
    profiles: Path

    @classmethod
    def from_env(cls) -> "RuntimeDirs":
        return cls(
            work=ensure_dir(_env("CRAWLER_WORK_DIR", "runtime/work")),
            logs=ensure_dir(_env("CRAWLER_LOG_DIR", "runtime/logs")),
            cache=ensure_dir(_env("CRAWLER_CACHE_DIR", "runtime/cache")),
            profiles=ensure_dir(_env("CRAWLER_PROFILE_DIR", "runtime/profiles")),
        )


@dataclass(slots=True)
class TaskContext:
    run_id: str
    company_id: str
    project_id: str
    project_code: str
    task_id: str
    task_code: str
    task_group: str
    runtime_mode: str
    io_class: str
    release_version: str
    build_sha: str
    image_digest: str
    shard_index: int | None
    shard_count: int | None
    resource_locks: list[Any]
    payload: dict[str, Any]
    dirs: RuntimeDirs
    logger: TaskLogger
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls, payload: dict[str, Any] | None = None) -> "TaskContext":
        env_payload = loads_dict(_env("CRAWLER_TASK_PARAMS_JSON", "{}"))
        data = {**env_payload, **(payload or {})}
        dirs = RuntimeDirs.from_env()
        shard_index = _first_env("CRAWLER_SHARD_INDEX", "SHARD_INDEX")
        shard_count = _first_env("CRAWLER_SHARD_COUNT", "SHARD_COUNT")
        run_id = _first_env("CRAWLER_RUN_ID", "RUN_ID", default="local-run")
        task_code = _first_env("CRAWLER_TASK_CODE", "TASK_CODE", default=str(data.get("taskCode") or data.get("task_code") or "local-task"))
        company_id = _first_env("CRAWLER_COMPANY_ID", "COMPANY_ID", default=str(data.get("companyId") or data.get("company_id") or ""))
        base_context = {
            "releaseVersion": _first_env("CRAWLER_RELEASE_VERSION", "RELEASE_VERSION", default=__version__),
            "buildSha": _first_env("CRAWLER_BUILD_SHA", "BUILD_SHA", "GIT_COMMIT", default="local"),
            "companyId": company_id,
            "projectId": _first_env("CRAWLER_PROJECT_ID", "PROJECT_ID", default=str(data.get("projectId") or data.get("project_id") or "")),
            "projectCode": _first_env("CRAWLER_PROJECT_CODE", "PROJECT_CODE", default=str(data.get("projectCode") or data.get("project_code") or "")),
            "taskId": _first_env("CRAWLER_TASK_ID", "TASK_ID", default=str(data.get("taskId") or data.get("task_id") or "")),
            "taskCode": task_code,
            "taskGroup": _first_env("CRAWLER_TASK_GROUP", "TASK_GROUP", default=str(data.get("taskGroup") or data.get("task_group") or "default")),
            "runId": run_id,
        }
        logger = create_logger(base_context=base_context, last_error_file=dirs.logs / f"{run_id}.last_error.json")
        return cls(
            run_id=run_id,
            company_id=base_context["companyId"],
            project_id=base_context["projectId"],
            project_code=base_context["projectCode"],
            task_id=base_context["taskId"],
            task_code=task_code,
            task_group=base_context["taskGroup"],
            runtime_mode=_first_env("CRAWLER_RUNTIME_MODE", "RUNTIME_MODE", default="SHARED_ENV_ISOLATED"),
            io_class=_first_env("CRAWLER_IO_CLASS", "IO_CLASS", default="NORMAL"),
            release_version=base_context["releaseVersion"],
            build_sha=base_context["buildSha"],
            image_digest=_first_env("CRAWLER_IMAGE_DIGEST", "IMAGE_DIGEST"),
            shard_index=_safe_int(shard_index),
            shard_count=_safe_int(shard_count),
            resource_locks=loads_list(_env("CRAWLER_RESOURCE_LOCKS_JSON", "[]")),
            payload=data,
            dirs=dirs,
            logger=logger,
        )
