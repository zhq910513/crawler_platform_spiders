#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler_foundation.tasks.discovery import discover_tasks
from crawler_foundation.tasks.registry import load_tasks
from scripts.sync_sch import render


def main() -> int:
    sch_path = ROOT / "sch.py"
    discovered_tasks = discover_tasks(ROOT)
    if not discovered_tasks:
        raise RuntimeError("没有在 spiders/ 下发现任何 TASK_DEFINITION/TASKS")
    expected_sch = render(discovered_tasks)
    actual_sch = sch_path.read_text(encoding="utf-8") if sch_path.exists() else ""
    if actual_sch != expected_sch:
        raise RuntimeError("sch.py 与 spiders 下的完整任务定义不一致，请执行：python scripts/sync_sch.py --write")
    sch_tasks = load_tasks(sch_path)
    for task in sch_tasks:
        module = importlib.import_module(task["entryModule"])
        target = getattr(module, task.get("entryFunction") or "run")
        if not callable(target):
            raise RuntimeError(f"任务入口不可调用：{task['entryModule']}:{task.get('entryFunction')}")
    print(f"任务清单检查通过，共 {len(sch_tasks)} 个任务；sch.py 与 spiders 完整任务定义一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
