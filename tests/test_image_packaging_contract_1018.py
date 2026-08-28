from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_python_build_backend_contract_is_explicit() -> None:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    build_system = payload["build-system"]
    assert build_system["build-backend"] == "setuptools.build_meta"
    assert "setuptools>=68" in build_system["requires"]
    assert "wheel" in build_system["requires"]


def test_dockerfiles_preinstall_declared_build_dependencies() -> None:
    for name in ("Dockerfile", "Dockerfile.browser"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert 'python -m pip install --upgrade pip "setuptools>=68" wheel -i ${PIP_INDEX_URL}' in text
        assert "python -m pip install --no-build-isolation --no-deps -e ." in text
        assert "ARG CRAWLER_RELEASE_VERSION=1.0.18" in text


def test_deprecated_active_release_files_are_absent() -> None:
    assert not (ROOT / ".github" / "workflows" / "crawler-platform-spider-release.yml").exists()
    assert not (ROOT / ".github" / "workflows" / "crawler-platform-spiders.yml").exists()
    assert not (ROOT / "crawler_project.example.json").exists()
    assert not (ROOT / "scripts" / "platform_register.py").exists()
