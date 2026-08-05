#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pprint
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler_foundation.core.files import atomic_write_text
from crawler_foundation.tasks.discovery import discover_tasks

HEADER = '''# -*- coding: utf-8 -*-
"""crawler_platform 静态任务清单。

本文件由 `python scripts/sync_sch.py --write` 根据 /spiders 下的 TASK_DEFINITION/TASKS 生成。
平台接入脚本会用 ast.literal_eval 静态解析 TASKS，因此本文件必须保持纯静态字面量。
新增平台爬虫时，只在 /spiders 或 /open_api 中增加业务代码，然后运行 sync_sch.py 生成本文件。
"""

'''


def render(tasks: list[dict]) -> str:
    return HEADER + "TASKS = " + pprint.pformat(tasks, width=120, sort_dicts=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync root sch.py from static task definitions under spiders/.")
    parser.add_argument("--write", action="store_true", help="write sch.py")
    parser.add_argument("--check", action="store_true", help="fail if sch.py is not synchronized")
    parser.add_argument("--output", default=str(ROOT / "sch.py"))
    args = parser.parse_args()
    tasks = discover_tasks(ROOT)
    if not tasks:
        raise RuntimeError("没有在 spiders/ 下发现任何 TASK_DEFINITION/TASKS")
    content = render(tasks)
    target = Path(args.output)
    if args.check:
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        if existing != content:
            print("sch.py 与 spiders 任务定义不一致，请执行：python scripts/sync_sch.py --write", file=sys.stderr)
            return 1
    if args.write:
        atomic_write_text(target, content)
        print(f"已生成 {target}，共 {len(tasks)} 个任务")
    if not args.write and not args.check:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
