from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from crawler_foundation.accounts import AccountCredential, AccountStatusReporter
from crawler_foundation.core.context import TaskContext


def test_context_config_resolver_uses_runtime_config_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CRAWLER_RUN_ID", "cfg-run")
    monkeypatch.setenv("CRAWLER_TASK_CODE", "cfg-task")
    monkeypatch.setenv("CRAWLER_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("CRAWLER_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("CRAWLER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CRAWLER_PROFILE_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("CRAWLER_CONFIG_JSON", json.dumps({"configs": {"mysql_main": {"host": "db", "password": "secret"}}, "configBindings": {"redis_cookie": "config:redis_cookie"}}))
    context = TaskContext.from_env({})
    assert context.config.mysql("mysql_main")["host"] == "db"
    assert context.config.redis("redis_cookie") == "config:redis_cookie"
    assert context.config.safe_dict()["configs"]["mysql_main"]["password"] == "***REDACTED***"


def test_reporter_uses_default_payload_and_platform_lease(tmp_path: Path) -> None:
    payload = {
        "accounts": {
            "worker": {"mode": "fixed", "credential": {"platformCode": "demo", "credentialKey": "account_a"}}
        }
    }
    reporter = AccountStatusReporter(company_code="ulike", run_id="100", task_id="200", spool_dir=tmp_path, payload=payload, lease_acquire_endpoint="http://platform/lease/acquire", lease_release_endpoint="http://platform/lease/release", token="Agent token")
    calls: list[tuple[str, dict]] = []

    def fake_post(endpoint: str, data: dict):
        calls.append((endpoint, data))
        if endpoint.endswith("acquire"):
            return {"data": {"lease": {"leaseId": 9}, "leaseToken": "lease-token"}}
        return {"data": {"released": True}}

    with patch.object(reporter, "_post_json", side_effect=fake_post):
        with reporter.lease("worker") as account:
            assert account.credential_key == "account_a"

    assert calls[0][0].endswith("acquire")
    assert calls[0][1]["credentialKey"] == "account_a"
    assert calls[-1][0].endswith("release")
    assert calls[-1][1]["leaseId"] == 9
