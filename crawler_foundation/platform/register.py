from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from crawler_foundation import __version__
from crawler_foundation.core.config import load_dotenv
from crawler_foundation.core.json_utils import read_json, write_json
from crawler_foundation.tasks.registry import build_manifest, load_tasks

ROOT = Path(__file__).resolve().parents[2]
ZERO_DIGEST = "sha256:" + "0" * 64


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, cwd=str(ROOT), stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def _split_server_codes(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in str(value or "").split(","):
            code = item.strip()
            if code and code not in seen:
                result.append(code)
                seen.add(code)
    return result


def _platform_endpoint(platform_url: str) -> str:
    base = platform_url.rstrip("/")
    if base.endswith("/api/v1"):
        return base + "/discovered-projects"
    return base + "/api/v1/discovered-projects"


def _server_payload(company_id: int, manifest: dict[str, Any], server_codes: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {"manifest": manifest}
    if company_id > 0:
        payload["companyId"] = company_id
    if server_codes:
        payload["serverCodes"] = server_codes
        payload["serverCode"] = server_codes[0]
    return payload


def _post_json(url: str, payload: dict[str, Any], *, discovery_token: str, timeout: int = 30) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Discovery {discovery_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"crawler_platform_spiders/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is operator/platform configured.
            text = response.read().decode("utf-8", errors="replace")
            if not text.strip():
                return {"status": response.status, "body": ""}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"status": response.status, "body": text}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"平台注册失败：HTTP {exc.code} {text[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"平台注册失败：无法连接 {url}，error={exc}") from exc


@dataclass(frozen=True, slots=True)
class RegisterOptions:
    platform_url: str
    discovery_token: str
    company_id: int = 0
    company_code: str = ""
    server_codes: list[str] = field(default_factory=list)
    project_key: str = "crawler_platform_spiders"
    project_code: str = "crawler_platform_spiders"
    project_name: str = "通用爬虫项目基建"
    image_repository: str = "crawler_platform_spiders"
    image_digest: str = ZERO_DIGEST
    release_version: str = __version__
    release_channel: str = "stable"
    repository_url: str = ""
    git_branch: str = ""
    git_commit: str = ""
    sch_path: str = "sch.py"
    manifest_path: str = ""
    output_manifest: str = ".release/crawler_manifest.json"
    request_output: str = ".release/discovered-project.json"
    dry_run: bool = False
    timeout: int = 30
    supported_arch: str = "linux/amd64"


def build_manifest_from_options(options: RegisterOptions) -> dict[str, Any]:
    if options.manifest_path:
        manifest = read_json(options.manifest_path)
        if not isinstance(manifest, dict):
            raise RuntimeError(f"manifest 必须是 JSON 对象：{options.manifest_path}")
        return manifest
    return build_manifest(
        tasks=load_tasks(ROOT / options.sch_path),
        project_key=options.project_key,
        project_code=options.project_code,
        project_name=options.project_name,
        image_repository=options.image_repository,
        image_digest=options.image_digest,
        release_version=options.release_version,
        release_channel=options.release_channel,
        repository_url=options.repository_url,
        git_branch=options.git_branch,
        git_commit=options.git_commit,
        company_code=options.company_code,
        supported_arch=options.supported_arch,
    )


def _validate_options(options: RegisterOptions) -> None:
    if not options.platform_url:
        raise RuntimeError("缺少平台地址：请传 --platform-url 或设置 CRAWLER_PLATFORM_URL")
    if not options.discovery_token:
        raise RuntimeError("缺少 Discovery token：请传 --discovery-token 或设置 CRAWLER_PLATFORM_DISCOVERY_TOKEN")
    if options.company_id <= 0 and not options.company_code:
        raise RuntimeError("缺少项目归属：请传 --company-id，或传 --company-code / 设置 CRAWLER_COMPANY_CODE")
    if options.company_code and not re.match(r"^[A-Za-z0-9_.-]{2,100}$", options.company_code):
        raise RuntimeError("companyCode 只允许字母、数字、下划线、点和横线，长度 2-100")
    # serverCodes is optional for crawler_platform >= 1.0.13.  CI/CD should
    # register one immutable release first; operators then decide which Agent
    # nodes join the project server pool in the platform UI.  Supplying
    # serverCodes remains supported for backward compatibility and initial
    # pool hints.
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", options.release_version or ""):
        raise RuntimeError("releaseVersion 必须是不可变语义版本，例如 1.0.13；禁止使用 main/latest/dev 或 v 前缀")
    if options.release_version != __version__:
        raise RuntimeError(f"releaseVersion={options.release_version} 与项目 VERSION={__version__} 不一致，请先递增版本并同步 sch.py")
    if not options.image_repository:
        raise RuntimeError("缺少镜像仓库：请传 --image-repository 或设置 IMAGE_REPOSITORY")
    if not options.image_digest.startswith("sha256:") or len(options.image_digest) != 71:
        raise RuntimeError("imageDigest 必须是 sha256: 加 64 位十六进制摘要")


def register_project_release(options: RegisterOptions) -> list[dict[str, Any]]:
    _validate_options(options)
    manifest = build_manifest_from_options(options)
    write_json(options.output_manifest, manifest)
    server_codes = options.server_codes or []
    payload = _server_payload(options.company_id, manifest, server_codes)
    write_json(options.request_output, payload)
    if options.dry_run:
        return [{"dryRun": True, "companyId": options.company_id or None, "companyCode": options.company_code or manifest.get("companyCode") or None, "serverCodes": server_codes, "releaseOnly": not bool(server_codes), "taskCount": len(manifest.get("taskDefinitions") or [])}]
    endpoint = _platform_endpoint(options.platform_url)
    return [_post_json(endpoint, payload, discovery_token=options.discovery_token, timeout=options.timeout)]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register this spider project release to crawler_platform.")
    parser.add_argument("--env-file", default=".env.platform", help="platform integration env file")
    parser.add_argument("--platform-url", default="")
    parser.add_argument("--discovery-token", default="")
    parser.add_argument("--company-id", type=int, default=0)
    parser.add_argument("--company-code", default="", help="project owner companyCode for crawler_platform >= 1.0.87 external CI registration")
    parser.add_argument("--server-code", action="append", default=[], help="optional initial Agent/server code hint; can be repeated or comma separated")
    parser.add_argument("--project-key", default="")
    parser.add_argument("--project-code", default="")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--image-repository", default="")
    parser.add_argument("--image-digest", default="")
    parser.add_argument("--release-version", default="")
    parser.add_argument("--release-channel", default="")
    parser.add_argument("--repository-url", default="")
    parser.add_argument("--git-branch", default="")
    parser.add_argument("--git-commit", default="")
    parser.add_argument("--sch", default="sch.py")
    parser.add_argument("--manifest", default="", help="use an existing manifest json instead of building from sch.py")
    parser.add_argument("--output-manifest", default=".release/crawler_manifest.json")
    parser.add_argument("--request-output", default=".release/discovered-project.json")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--supported-arch", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def options_from_args(argv: Sequence[str] | None = None) -> RegisterOptions:
    args = _parser().parse_args(argv)
    load_dotenv(args.env_file)
    raw_server_codes = args.server_code or [_env("CRAWLER_PLATFORM_SERVER_CODES", "CRAWLER_PLATFORM_SERVER_CODE", "SERVER_CODES", "SERVER_CODE")]
    return RegisterOptions(
        platform_url=args.platform_url or _env("CRAWLER_PLATFORM_URL", "PLATFORM_URL"),
        discovery_token=args.discovery_token or _env("CRAWLER_PLATFORM_DISCOVERY_TOKEN", "DISCOVERY_TOKEN"),
        company_id=args.company_id or int(_env("CRAWLER_PLATFORM_COMPANY_ID", "COMPANY_ID", default="0")),
        company_code=args.company_code or _env("CRAWLER_COMPANY_CODE", "COMPANY_CODE"),
        server_codes=_split_server_codes(raw_server_codes),
        project_key=args.project_key or _env("PROJECT_KEY", default="crawler_platform_spiders"),
        project_code=args.project_code or _env("PROJECT_CODE", default="crawler_platform_spiders"),
        project_name=args.project_name or _env("PROJECT_NAME", default="通用爬虫项目基建"),
        image_repository=args.image_repository or _env("IMAGE_REPOSITORY", default="crawler_platform_spiders"),
        image_digest=args.image_digest or _env("IMAGE_DIGEST", "CRAWLER_IMAGE_DIGEST", default=ZERO_DIGEST),
        release_version=args.release_version or _env("RELEASE_VERSION", "CRAWLER_RELEASE_VERSION", default=__version__),
        release_channel=args.release_channel or _env("RELEASE_CHANNEL", default="stable"),
        repository_url=args.repository_url or _env("REPOSITORY_URL", default=_git(["git", "config", "--get", "remote.origin.url"])),
        git_branch=args.git_branch or _env("GIT_BRANCH", default=_git(["git", "rev-parse", "--abbrev-ref", "HEAD"])),
        git_commit=args.git_commit or _env("GIT_COMMIT", "CRAWLER_BUILD_SHA", default=_git(["git", "rev-parse", "--short=12", "HEAD"])),
        sch_path=args.sch,
        manifest_path=args.manifest,
        output_manifest=args.output_manifest,
        request_output=args.request_output,
        dry_run=bool(args.dry_run),
        timeout=args.timeout,
        supported_arch=args.supported_arch or _env("CRAWLER_SUPPORTED_ARCH", "SUPPORTED_ARCH", default="linux/amd64"),
    )


def cli_main(argv: Sequence[str] | None = None) -> int:
    try:
        options = options_from_args(argv)
        responses = register_project_release(options)
        print(json.dumps({"ok": True, "dryRun": options.dry_run, "serverCodes": options.server_codes, "responses": responses}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli_main())
