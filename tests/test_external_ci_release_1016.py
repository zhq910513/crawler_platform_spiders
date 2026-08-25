from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_standard_github_external_release_workflow_exists() -> None:
    workflow = ROOT / ".github" / "workflows" / "crawler-platform-spider-release.yml"
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")
    assert "scripts/platform_register.py" in text
    assert "CRAWLER_COMPANY_CODE" in text
    assert "CRAWLER_DISCOVERY_TOKEN" in text
    assert "Configure insecure HTTP registry" in text
    assert "docker/build-push-action@v6" in text
    assert not (ROOT / ".github" / "workflows" / "crawler-platform-spiders.yml").exists()


def test_platform_register_company_code_dry_run_payload(tmp_path: Path) -> None:
    manifest = tmp_path / "crawler_manifest.json"
    request_file = tmp_path / "discovered-project.json"
    digest = "sha256:" + "6" * 64
    result = subprocess.run(
        [
            sys.executable,
            "scripts/platform_register.py",
            "--platform-url",
            "http://crawler-platform.local",
            "--discovery-token",
            "secret-token",
            "--company-code",
            "demo_company",
            "--project-key",
            "crawler_platform_spiders",
            "--project-code",
            "crawler_platform_spiders",
            "--project-name",
            "通用爬虫项目基建",
            "--image-repository",
            "registry.local/crawler_platform_spiders",
            "--image-digest",
            digest,
            "--release-version",
            "1.0.16",
            "--output-manifest",
            str(manifest),
            "--request-output",
            str(request_file),
            "--dry-run",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["companyCode"] == "demo_company"
    assert manifest_payload["releaseVersion"] == "1.0.16"
    assert manifest_payload["imageDigest"] == digest
    assert manifest_payload["supportedArch"] == "linux/amd64"
    request_payload = json.loads(request_file.read_text(encoding="utf-8"))
    assert "companyId" not in request_payload
    assert request_payload["manifest"]["companyCode"] == "demo_company"
    assert request_payload["manifest"]["taskDefinitions"]


def test_build_manifest_includes_company_code_from_env(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"
    env = {
        "PROJECT_KEY": "crawler_platform_spiders",
        "PROJECT_CODE": "crawler_platform_spiders",
        "PROJECT_NAME": "通用爬虫项目基建",
        "IMAGE_REPOSITORY": "registry.local/crawler_platform_spiders",
        "IMAGE_DIGEST": "sha256:" + "7" * 64,
        "RELEASE_VERSION": "1.0.16",
        "CRAWLER_COMPANY_CODE": "demo_company",
    }
    import os

    run_env = os.environ.copy()
    run_env.update(env)
    result = subprocess.run(
        [sys.executable, "scripts/build_manifest.py", "--output", str(output)],
        cwd=str(ROOT),
        env=run_env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["companyCode"] == "demo_company"
    assert payload["supportedArch"] == "linux/amd64"
    assert payload["taskDefinitions"]


def test_crawler_project_example_is_not_real_secret_config() -> None:
    example = json.loads((ROOT / "crawler_project.example.json").read_text(encoding="utf-8"))
    assert example["companyCode"] == "replace_with_company_code_from_crawler_platform"
    assert "token" not in json.dumps(example).lower()
