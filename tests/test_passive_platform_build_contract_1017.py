from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_active_cicd_workflow_or_project_registration_config() -> None:
    assert not (ROOT / ".github" / "workflows" / "crawler-platform-spider-release.yml").exists()
    assert not (ROOT / "crawler_project.example.json").exists()
    assert not (ROOT / "crawler_project.json").exists()
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "CRAWLER_DISCOVERY_TOKEN" not in env_example
    assert "CRAWLER_CONTROL_BASE_URL" not in env_example
    assert "CRAWLER_REGISTRY_USERNAME" not in env_example
    assert "CRAWLER_REGISTRY_PASSWORD" not in env_example


def test_active_register_entrypoints_are_removed() -> None:
    assert not (ROOT / "scripts" / "platform_register.py").exists()
    platform_init = (ROOT / "crawler_foundation" / "platform" / "__init__.py").read_text(encoding="utf-8")
    cli = (ROOT / "crawler_foundation" / "cli.py").read_text(encoding="utf-8")
    assert "register_cli_main" not in cli
    assert "sub.add_parser(\"register\"" not in cli
    assert "不主动调用 crawler_platform 注册 Release" in platform_init


def test_passive_build_contract_script_generates_manifest(tmp_path: Path) -> None:
    output = tmp_path / "crawler_manifest.json"
    env = os.environ.copy()
    env.update(
        {
            "OUTPUT_MANIFEST": str(output),
            "PROJECT_KEY": "crawler_platform_spiders",
            "PROJECT_CODE": "crawler_platform_spiders",
            "PROJECT_NAME": "通用爬虫项目基建",
            "IMAGE_REPOSITORY": "registry.local/crawler_platform_spiders",
            "IMAGE_DIGEST": "sha256:" + "8" * 64,
            "RELEASE_VERSION": "1.0.18",
            "GIT_COMMIT": "pytest-passive-build",
        }
    )
    result = subprocess.run(
        ["bash", "scripts/platform_build_contract.sh"],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASSIVE_BUILD_CONTRACT_OK" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["releaseVersion"] == "1.0.18"
    assert payload["imageDigest"] == "sha256:" + "8" * 64
    assert payload["taskDefinitions"]


def test_deprecated_build_and_register_fails_closed() -> None:
    result = subprocess.run(
        ["bash", "scripts/build_and_register.sh"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 2
    assert "已废弃" in result.stderr
    assert "不主动 CI/CD" in result.stderr
