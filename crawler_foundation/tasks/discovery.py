from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from crawler_foundation.tasks.registry import REQUIRED_TASK_KEYS

EXCLUDED_DIRS = {"common", "__pycache__"}
EXCLUDED_FILES = {"__init__.py"}


def _literal_assignment(tree: ast.Module, names: set[str]) -> ast.AST | None:
    result: ast.AST | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    result = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in names:
            result = node.value
    return result


def _has_callable(tree: ast.Module, name: str) -> bool:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return True
    return False


def _module_name(root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def _normalize_task(item: dict[str, Any], *, module_name: str, source_file: str, index: int) -> dict[str, Any]:
    task = {str(k): v for k, v in item.items()}
    task.setdefault("entryModule", module_name)
    task.setdefault("entryFunction", "run")
    task.setdefault("sourceFile", source_file)
    missing = sorted(REQUIRED_TASK_KEYS - set(task))
    if missing:
        raise RuntimeError(f"{source_file} 第 {index} 个任务定义缺少字段：{', '.join(missing)}")
    for field in ("definitionKey", "taskName", "entryModule", "entryFunction"):
        if not str(task.get(field) or "").strip():
            raise RuntimeError(f"{source_file} 第 {index} 个任务定义字段不能为空：{field}")
    return task


def discover_tasks(root: str | Path = ".", spiders_dir: str | Path = "spiders") -> list[dict[str, Any]]:
    """从 spiders 目录静态发现任务定义。

    约定：业务模块中声明纯字面量 `TASK_DEFINITION = {...}` 或 `TASKS = [{...}]`。
    本函数只做 AST + literal_eval，不 import 业务模块，避免扫描阶段触发登录、请求、数据库连接等副作用。
    """

    base = Path(root).resolve()
    target = (base / spiders_dir).resolve()
    if not target.exists():
        return []
    tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for file_path in sorted(target.rglob("*.py")):
        rel_parts = file_path.relative_to(target).parts
        if file_path.name in EXCLUDED_FILES or any(part in EXCLUDED_DIRS for part in rel_parts[:-1]):
            continue
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except SyntaxError as exc:
            raise RuntimeError(f"{file_path.relative_to(base)} Python 语法错误：{exc}") from exc
        node = _literal_assignment(tree, {"TASK_DEFINITION", "TASKS"})
        if node is None:
            continue
        module_name = _module_name(base, file_path)
        source_file = str(file_path.relative_to(base)).replace("\\", "/")
        try:
            value = ast.literal_eval(node)
        except Exception as exc:
            raise RuntimeError(f"{source_file} 的 TASK_DEFINITION/TASKS 必须是纯静态字面量，不能调用函数、读取变量或读取环境") from exc
        raw_tasks = value if isinstance(value, list) else [value]
        if not isinstance(raw_tasks, list):
            raise RuntimeError(f"{source_file} 的任务定义必须是字典或字典列表")
        for index, raw in enumerate(raw_tasks, start=1):
            if not isinstance(raw, dict):
                raise RuntimeError(f"{source_file} 第 {index} 个任务定义必须是字典")
            task = _normalize_task(raw, module_name=module_name, source_file=source_file, index=index)
            entry_function = str(task.get("entryFunction") or "run")
            if not _has_callable(tree, entry_function):
                raise RuntimeError(f"{source_file} 缺少任务入口函数：{entry_function}")
            key = str(task["definitionKey"])
            if key in seen:
                raise RuntimeError(f"发现重复 definitionKey：{key}")
            seen.add(key)
            tasks.append(task)
    return tasks
