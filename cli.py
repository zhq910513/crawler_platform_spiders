from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from crawler_platform_spiders import APP_NAME, __version__
from crawler_platform_spiders.registry import list_tasks
from crawler_platform_spiders.runner import RunOptions, run_task


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crawler-platform-spiders")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run one registered spider task")
    run.add_argument("--mode", choices=("local", "server"), required=True)
    run.add_argument("--task-file", type=Path, required=True)
    run.add_argument("--resources-file", type=Path, required=True)
    run.add_argument("--secrets-file", type=Path, required=True)
    run.add_argument("--result-file", type=Path, required=True)
    run.add_argument("--errors-file", type=Path)
    run.add_argument("--last-error-file", type=Path)
    run.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    run.add_argument("--human-logs", action="store_true")

    manifest = subparsers.add_parser("manifest", help="Print immutable spider release manifest")
    manifest.add_argument("--output", type=Path)
    return parser


def _manifest() -> dict:
    return {
        "schema_version": "1.0",
        "app_name": APP_NAME,
        "version": os.getenv("CRAWLER_RELEASE_VERSION", __version__),
        "build_sha": os.getenv("CRAWLER_BUILD_SHA", "dev"),
        "image_digest": os.getenv("CRAWLER_IMAGE_DIGEST") or None,
        "entries": [
            {
                "task_name": item.name,
                "description": item.description,
                "image_profile": item.image_profile,
                "default_timeout_seconds": item.default_timeout_seconds,
                "required_resources": list(item.required_resources),
                "parameter_schema": item.parameter_schema(),
            }
            for item in list_tasks()
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "manifest":
        payload = _manifest()
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content + "\n", encoding="utf-8")
        else:
            print(content)
        return 0

    result_dir = args.result_file.parent
    errors_file = args.errors_file or result_dir / "errors.ndjson"
    last_error_file = args.last_error_file or result_dir / "last_error.json"
    human_logs = bool(args.human_logs and args.mode == "local")
    return run_task(
        RunOptions(
            mode=args.mode,
            task_file=args.task_file,
            resources_file=args.resources_file,
            secrets_file=args.secrets_file,
            result_file=args.result_file,
            errors_file=errors_file,
            last_error_file=last_error_file,
            log_level=args.log_level,
            human_logs=human_logs,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
