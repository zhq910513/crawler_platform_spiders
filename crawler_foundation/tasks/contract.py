from __future__ import annotations

import re
from typing import Any

TASK_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,95}$")
PLATFORM_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
SLOT_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
SUPPORTED_CREDENTIAL_MODES = {
    "fixed",
    "fixed_list",
    "pool",
    "binding_rule",
    "affinity_pool",
    "external_affinity_pool",
}
SUPPORTED_CONFIG_TYPES = {"MYSQL", "REDIS", "MONGO", "OSS", "HTTP", "BROWSER", "CUSTOM"}
SUPPORTED_WRITE_METHODS = {"insert", "replace", "insert_ignore", "upsert", "update"}


def _as_list(value: Any, *, field: str, task_key: str) -> list[Any]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise RuntimeError(f"任务 {task_key} 的 {field} 必须是列表")
    return value


def _require_slot(item: dict[str, Any], *, field: str, task_key: str) -> str:
    slot = str(item.get("slot") or "").strip()
    if not SLOT_RE.match(slot):
        raise RuntimeError(f"任务 {task_key} 的 {field}.slot 不合法：{slot}")
    return slot


def validate_task_contract(task: dict[str, Any]) -> list[str]:
    """Validate the public task contract used by crawler_platform.

    The function returns warnings and raises RuntimeError for release-blocking
    problems.  It is static and does not import business modules.
    """

    task_key = str(task.get("definitionKey") or "").strip()
    if not TASK_KEY_RE.match(task_key):
        raise RuntimeError(f"任务 definitionKey 不合法：{task_key}")
    platform_code = str(task.get("platformCode") or "").strip()
    if not PLATFORM_RE.match(platform_code):
        raise RuntimeError(f"任务 {task_key} 的 platformCode 不合法：{platform_code}")
    entry_module = str(task.get("entryModule") or "").strip()
    entry_function = str(task.get("entryFunction") or "").strip()
    if not entry_module.startswith("spiders."):
        raise RuntimeError(f"任务 {task_key} 的 entryModule 必须位于 spiders 包下")
    if not entry_function:
        raise RuntimeError(f"任务 {task_key} 的 entryFunction 不能为空")

    warnings: list[str] = []
    config_slots: set[str] = set()
    for item in _as_list(task.get("requiredConfigs"), field="requiredConfigs", task_key=task_key):
        if not isinstance(item, dict):
            raise RuntimeError(f"任务 {task_key} 的 requiredConfigs 项必须是对象")
        slot = _require_slot(item, field="requiredConfigs", task_key=task_key)
        if slot in config_slots:
            raise RuntimeError(f"任务 {task_key} 的 requiredConfigs 槽位重复：{slot}")
        config_slots.add(slot)
        cfg_type = str(item.get("type") or item.get("configType") or "CUSTOM").upper()
        if cfg_type not in SUPPORTED_CONFIG_TYPES:
            raise RuntimeError(f"任务 {task_key} 的配置槽位 {slot} 类型不支持：{cfg_type}")

    credential_slots: set[str] = set()
    for item in _as_list(task.get("requiredCredentials"), field="requiredCredentials", task_key=task_key):
        if not isinstance(item, dict):
            raise RuntimeError(f"任务 {task_key} 的 requiredCredentials 项必须是对象")
        slot = _require_slot(item, field="requiredCredentials", task_key=task_key)
        if slot in credential_slots:
            raise RuntimeError(f"任务 {task_key} 的 requiredCredentials 槽位重复：{slot}")
        credential_slots.add(slot)
        modes = item.get("supportedModes") or item.get("modes") or []
        if isinstance(modes, str):
            modes = [modes]
        if not isinstance(modes, list) or not modes:
            raise RuntimeError(f"任务 {task_key} 的账号槽位 {slot} 必须声明 supportedModes")
        invalid_modes = sorted(str(mode) for mode in modes if str(mode) not in SUPPORTED_CREDENTIAL_MODES)
        if invalid_modes:
            raise RuntimeError(f"任务 {task_key} 的账号槽位 {slot} 模式不支持：{', '.join(invalid_modes)}")
        if str(item.get("platformCode") or platform_code) != platform_code:
            warnings.append(f"账号槽位 {slot} platformCode 与任务 platformCode 不一致，请确认跨平台账号是否必要")
        if any(mode in {"affinity_pool", "external_affinity_pool"} for mode in modes):
            affinity = item.get("affinity") if isinstance(item.get("affinity"), dict) else {}
            subject_type = str(item.get("subjectType") or affinity.get("subjectType") or "").strip()
            if not subject_type:
                raise RuntimeError(f"任务 {task_key} 的亲和账号槽位 {slot} 必须声明 subjectType 或 affinity.subjectType")

    output_slots: set[str] = set()
    for item in _as_list(task.get("outputTables"), field="outputTables", task_key=task_key):
        if not isinstance(item, dict):
            raise RuntimeError(f"任务 {task_key} 的 outputTables 项必须是对象")
        slot = _require_slot(item, field="outputTables", task_key=task_key)
        if slot in output_slots:
            raise RuntimeError(f"任务 {task_key} 的 outputTables 槽位重复：{slot}")
        output_slots.add(slot)
        write_method = str(item.get("writeMethod") or "replace")
        if write_method not in SUPPORTED_WRITE_METHODS:
            raise RuntimeError(f"任务 {task_key} 的输出表 {slot} 写入方式不支持：{write_method}")
        default_name = str(item.get("defaultName") or "").strip()
        if not default_name:
            warnings.append(f"输出表 {slot} 未声明默认表名，任务调度时必须显式绑定")

    return warnings


def validate_tasks_contract(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    warnings: dict[str, list[str]] = {}
    for task in tasks:
        task_warnings = validate_task_contract(task)
        if task_warnings:
            warnings[str(task.get("definitionKey"))] = task_warnings
    return {"taskCount": len(tasks), "warnings": warnings}
