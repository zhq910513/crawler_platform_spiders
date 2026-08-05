#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TASK_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,95}$")
_PLATFORM_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

TEMPLATE = '''from __future__ import annotations

from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task

TASK_DEFINITION = {{
    "definitionKey": "{definition_key}",
    "taskName": "{task_name}",
    "defaultParams": {{}},
    "suggestedCron": "",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "resourceRequirements": {{}},
    "requiredCapabilities": {{"browser": {browser}}},
    "runtimeMode": "SHARED_ENV_ISOLATED",
    "taskGroup": "{task_group}",
    "taskMaxConcurrency": 1,
    "groupMaxConcurrency": 4,
    "exclusiveMode": False,
    "ioClass": "NORMAL",
    "shmSizeMb": {shm_size_mb},
    "logLimitMb": 20,
    "resourceLocks": [],
    "secretRefs": [],
}}


@platform_task()
def run(context, **kwargs) -> TaskResult:
    """业务入口。

    只在本函数内编写平台爬虫逻辑；日志、上下文、退出码、平台参数过滤由公共层处理。
    """
    context.logger.info("任务开始执行业务占位逻辑", event="business_started", kwargs=kwargs)
    return TaskResult.success("任务模板执行成功", data={{"kwargs": kwargs}})
'''


def _module_file(platform: str, definition_key: str) -> Path:
    short_name = definition_key
    prefix = platform + "_"
    if short_name.startswith(prefix):
        short_name = short_name[len(prefix):]
    return ROOT / "spiders" / platform / f"{short_name}.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new spider task module template under spiders/<platform>/.")
    parser.add_argument("--platform", required=True, help="platform directory, e.g. amazon")
    parser.add_argument("--definition-key", required=True, help="unique task key, snake_case")
    parser.add_argument("--task-name", required=True, help="display task name")
    parser.add_argument("--task-group", help="default is platform")
    parser.add_argument("--browser", action="store_true", help="mark task as browser-capable")
    parser.add_argument("--write", action="store_true", help="write file; otherwise print target and preview")
    args = parser.parse_args()

    platform = args.platform.strip().lower()
    definition_key = args.definition_key.strip().lower()
    if not _PLATFORM_RE.match(platform):
        raise RuntimeError("--platform 必须是小写字母、数字、下划线组合，且以小写字母开头")
    if not _TASK_KEY_RE.match(definition_key):
        raise RuntimeError("--definition-key 必须是小写字母、数字、下划线组合，且以小写字母开头")

    target = _module_file(platform, definition_key)
    content = TEMPLATE.format(
        definition_key=definition_key,
        task_name=args.task_name.replace('"', '\\"'),
        task_group=(args.task_group or platform).strip().lower(),
        browser="True" if args.browser else "False",
        shm_size_mb=512 if args.browser else 64,
    )
    if target.exists():
        raise RuntimeError(f"目标文件已存在：{target.relative_to(ROOT)}")
    if not args.write:
        print(f"将创建：{target.relative_to(ROOT)}")
        print(content)
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    init_file = target.parent / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")
    target.write_text(content, encoding="utf-8")
    print(f"已创建：{target.relative_to(ROOT)}")
    print("下一步执行：python scripts/sync_sch.py --write && python scripts/validate_tasks.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
