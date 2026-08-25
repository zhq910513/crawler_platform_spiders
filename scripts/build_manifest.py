#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler_foundation import __version__
from crawler_foundation.tasks.registry import build_manifest, load_tasks


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, cwd=str(ROOT), stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="crawler_manifest.json")
    args = parser.parse_args()
    payload = build_manifest(
        tasks=load_tasks(ROOT / "sch.py"),
        project_key=os.getenv("PROJECT_KEY", "crawler_platform_spiders"),
        project_code=os.getenv("PROJECT_CODE", "crawler_platform_spiders"),
        project_name=os.getenv("PROJECT_NAME", "通用爬虫项目基建"),
        image_repository=os.getenv("IMAGE_REPOSITORY", "crawler_platform_spiders"),
        image_digest=os.getenv("IMAGE_DIGEST", "sha256:" + "0" * 64),
        release_version=os.getenv("RELEASE_VERSION", __version__),
        release_channel=os.getenv("RELEASE_CHANNEL", "stable"),
        repository_url=os.getenv("REPOSITORY_URL", git(["git", "config", "--get", "remote.origin.url"])),
        git_branch=os.getenv("GIT_BRANCH", git(["git", "rev-parse", "--abbrev-ref", "HEAD"])),
        git_commit=os.getenv("GIT_COMMIT", git(["git", "rev-parse", "--short=12", "HEAD"])),
        company_code=os.getenv("CRAWLER_COMPANY_CODE", os.getenv("COMPANY_CODE", "")),
        supported_arch=os.getenv("SUPPORTED_ARCH", os.getenv("CRAWLER_SUPPORTED_ARCH", "linux/amd64")),
    )
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
