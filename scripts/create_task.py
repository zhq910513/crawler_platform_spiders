#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler_foundation.development import ScaffoldOptions, module_file, render_task_template


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new standard spider task under spiders/<platform>/.")
    parser.add_argument("--platform", required=True, help="平台目录，例如 amazon / shopee / oilchem")
    parser.add_argument("--definition-key", required=True, help="任务唯一键，snake_case")
    parser.add_argument("--task-name", required=True, help="前端展示任务名称")
    parser.add_argument("--task-group", help="任务分组，默认等于平台编码")
    parser.add_argument("--task-kind", choices=["basic", "page", "subject", "api"], default="basic", help="模板类型")
    parser.add_argument("--table-name", default="", help="默认输出表名")
    parser.add_argument("--subject-type", default="company", help="对象亲和模板的对象类型")
    parser.add_argument("--browser", action="store_true", help="声明任务需要浏览器能力")
    parser.add_argument("--write", action="store_true", help="写入文件；不加则仅预览")
    args = parser.parse_args()

    opts = ScaffoldOptions(
        platform=args.platform,
        definition_key=args.definition_key,
        task_name=args.task_name,
        task_group=args.task_group or "",
        browser=args.browser,
        task_kind=args.task_kind,
        table_name=args.table_name,
        subject_type=args.subject_type,
    ).normalized()
    target = module_file(ROOT, opts)
    content = render_task_template(opts)
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
