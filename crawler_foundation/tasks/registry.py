from __future__ import annotations

import ast
import copy
import hashlib
from pathlib import Path
from typing import Any

REQUIRED_TASK_KEYS = {"definitionKey", "taskName", "entryModule", "entryFunction"}


def _literal_tasks_node(path: Path) -> ast.AST:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    task_node: ast.AST | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TASKS":
                    task_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "TASKS":
            task_node = node.value
    if task_node is None:
        raise RuntimeError("sch.py 必须声明静态 TASKS = [...] 任务清单")
    return task_node


def load_tasks(path: str | Path = "sch.py") -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"任务清单不存在：{target}")
    try:
        tasks = ast.literal_eval(_literal_tasks_node(target))
    except Exception as exc:
        raise RuntimeError("TASKS 必须是纯静态字面量，不能调用函数、读取环境变量或动态生成") from exc
    if not isinstance(tasks, list) or not tasks:
        raise RuntimeError("TASKS 必须是非空列表")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise RuntimeError(f"TASKS 第 {index} 项必须是字典")
        item = {str(k): copy.deepcopy(v) for k, v in task.items()}
        missing = sorted(REQUIRED_TASK_KEYS - set(item))
        if missing:
            raise RuntimeError(f"TASKS 第 {index} 项缺少字段：{', '.join(missing)}")
        key = str(item["definitionKey"])
        if key in seen:
            raise RuntimeError(f"TASKS 存在重复 definitionKey：{key}")
        seen.add(key)
        item.setdefault("sourceFingerprint", _fingerprint(item))
        normalized.append(item)
    return normalized


def _fingerprint(task: dict[str, Any]) -> str:
    raw = repr(sorted((str(k), repr(v)) for k, v in task.items())).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def resolve_task(path: str | Path, definition_key: str) -> dict[str, Any]:
    for task in load_tasks(path):
        if task.get("definitionKey") == definition_key:
            return task
    raise KeyError(f"未找到任务定义：{definition_key}")


def build_manifest(*, tasks: list[dict[str, Any]], project_key: str, project_code: str, project_name: str, image_repository: str, image_digest: str, release_version: str, release_channel: str = "stable", repository_url: str = "", git_branch: str = "", git_commit: str = "") -> dict[str, Any]:
    return {
        "manifestVersion": "1",
        "projectKey": project_key,
        "projectCode": project_code,
        "projectName": project_name,
        "repositoryUrl": repository_url,
        "imageRepository": image_repository,
        "imageDigest": image_digest,
        "gitBranch": git_branch,
        "gitCommit": git_commit,
        "releaseVersion": release_version,
        "releaseChannel": release_channel,
        "runtimeType": "python",
        "taskDefinitions": tasks,
    }
