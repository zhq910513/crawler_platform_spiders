from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from crawler_foundation.accounts import AccountCredential, AccountStatusReporter
from crawler_foundation.core.auth_cache import AuthCacheRecord
from crawler_foundation.core.batch import BatchWriter, iter_batches
from crawler_foundation.tasks.contract import validate_task_contract

ROOT = Path(__file__).resolve().parents[1]


def test_batch_writer_flushes_and_normalizes_rows() -> None:
    written: list[list[dict]] = []
    writer = BatchWriter(lambda rows: written.append(rows), batch_size=2)
    writer.add({"a": 1, "": "skip"})
    writer.add({"a": 2})
    writer.add({"a": 3})
    assert len(written) == 1
    assert written[0] == [{"a": 1}, {"a": 2}]
    writer.close()
    assert written[-1] == [{"a": 3}]
    assert list(iter_batches([1, 2, 3], 2)) == [[1, 2], [3]]


def test_auth_cache_record_supports_legacy_hash_key_and_masks_secret() -> None:
    record = AuthCacheRecord.from_mapping(
        {
            "companyCode": "ulike",
            "platformCode": "jdl",
            "hash_key": "jdl_main",
            "auth": {"accessToken": "token-123", "refreshToken": "refresh-456"},
            "status": {"healthStatus": "HEALTHY", "loginStatus": "AUTH_ACTIVE", "statusCode": "TOKEN_OK"},
        }
    )
    assert record.credential_key == "jdl_main"
    data = record.to_dict()
    assert data["fingerprint"]
    assert record.safe_dict()["auth"]["accessToken"] == "***REDACTED***"


def test_task_contract_rejects_invalid_credential_mode() -> None:
    task = {
        "definitionKey": "demo_bad_task",
        "taskName": "bad",
        "platformCode": "demo",
        "entryModule": "spiders.demo.bad",
        "entryFunction": "run",
        "requiredCredentials": [{"slot": "login", "platformCode": "demo", "supportedModes": ["random"]}],
        "requiredConfigs": [],
        "outputTables": [],
    }
    with pytest.raises(RuntimeError, match="模式不支持"):
        validate_task_contract(task)


def test_task_contract_requires_subject_type_for_affinity() -> None:
    task = {
        "definitionKey": "demo_subject_task",
        "taskName": "subject",
        "platformCode": "demo",
        "entryModule": "spiders.demo.subject_task",
        "entryFunction": "run",
        "requiredCredentials": [{"slot": "queryAccount", "platformCode": "demo", "supportedModes": ["affinity_pool"]}],
        "requiredConfigs": [],
        "outputTables": [],
    }
    with pytest.raises(RuntimeError, match="subjectType"):
        validate_task_contract(task)


def test_create_task_generates_subject_template_preview() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/create_task.py",
            "--platform",
            "pytest_subject",
            "--definition-key",
            "pytest_subject_company_query",
            "--task-name",
            "公司查询",
            "--task-kind",
            "subject",
            "--subject-type",
            "company",
            "--table-name",
            "pytest_company_info",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "StandardSubjectTask" in result.stdout
    assert "external_affinity_pool" in result.stdout
    assert "spiders/pytest_subject/company_query.py" in result.stdout.replace("\\", "/")
    assert not (ROOT / "spiders" / "pytest_subject" / "company_query.py").exists()


def test_account_pool_lease_can_use_platform_selected_credential(tmp_path: Path) -> None:
    payload = {
        "accounts": {
            "worker": {
                "mode": "pool",
                "platformCode": "demo",
                "selector": {"tags": {"purpose": "company_query"}},
            }
        }
    }
    reporter = AccountStatusReporter(
        company_code="ulike",
        run_id="101",
        task_id="201",
        spool_dir=tmp_path,
        payload=payload,
        lease_acquire_endpoint="http://platform/lease/acquire",
        lease_release_endpoint="http://platform/lease/release",
    )
    calls: list[tuple[str, dict]] = []

    def fake_post(endpoint: str, data: dict):
        calls.append((endpoint, data))
        if endpoint.endswith("acquire"):
            return {"data": {"lease": {"leaseId": 12, "credentialKey": "selected_a", "platformCode": "demo"}, "leaseToken": "lt"}}
        return {"data": {"released": True}}

    with patch.object(reporter, "_post_json", side_effect=fake_post):
        with reporter.lease("worker") as account:
            assert isinstance(account, AccountCredential)
            assert account.credential_key == "selected_a"

    assert calls[0][1]["mode"] == "pool"
    assert calls[0][1]["selector"] == {"tags": {"purpose": "company_query"}}
    assert calls[-1][1]["leaseId"] == 12
