from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from crawler_foundation import __version__
from crawler_foundation.core.config import load_dotenv
from crawler_foundation.core.json_utils import write_json
from crawler_foundation.tasks.registry import build_manifest, load_tasks, resolve_task
from crawler_runtime.__main__ import main as runtime_main
from crawler_foundation.platform.register import cli_main as register_cli_main


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crawler-platform-spiders")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("manifest", help="Print crawler_platform project manifest")
    manifest.add_argument("--sch", default="sch.py")
    manifest.add_argument("--output")
    run = sub.add_parser("run", help="Run a task locally by definitionKey in sch.py")
    run.add_argument("--sch", default="sch.py")
    run.add_argument("--task-code", required=True)
    run.add_argument("--kwargs-json", default="{}")
    run.add_argument("--env-file", default=".env")
    register = sub.add_parser("register", help="Register project release to crawler_platform")
    register.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed to scripts/platform_register.py")
    return parser


def _manifest_payload(sch: str) -> dict[str, Any]:
    return build_manifest(
        tasks=load_tasks(Path(sch)),
        project_key=os.getenv("PROJECT_KEY", "crawler_platform_spiders"),
        project_code=os.getenv("PROJECT_CODE", "crawler_platform_spiders"),
        project_name=os.getenv("PROJECT_NAME", "通用爬虫项目基建"),
        image_repository=os.getenv("IMAGE_REPOSITORY", "crawler_platform_spiders"),
        image_digest=os.getenv("IMAGE_DIGEST", "sha256:" + "0" * 64),
        release_version=os.getenv("RELEASE_VERSION", os.getenv("CRAWLER_RELEASE_VERSION", __version__)),
        release_channel=os.getenv("RELEASE_CHANNEL", "stable"),
        repository_url=os.getenv("REPOSITORY_URL", _git(["git", "config", "--get", "remote.origin.url"])),
        git_branch=os.getenv("GIT_BRANCH", _git(["git", "rev-parse", "--abbrev-ref", "HEAD"])),
        git_commit=os.getenv("GIT_COMMIT", _git(["git", "rev-parse", "--short=12", "HEAD"])),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv()
    if args.command == "manifest":
        payload = _manifest_payload(args.sch)
        if args.output:
            write_json(args.output, payload)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.command == "run":
        load_dotenv(args.env_file)
        task = resolve_task(Path(args.sch), args.task_code)
        entrypoint = f"{task['entryModule']}:{task.get('entryFunction') or 'run'}"
        return runtime_main(["--entrypoint", entrypoint, "--kwargs-json", args.kwargs_json])
    if args.command == "register":
        register_args = list(args.args)
        if register_args and register_args[0] == "--":
            register_args = register_args[1:]
        return register_cli_main(register_args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
