from __future__ import annotations

import json
from pathlib import Path

from crawler_foundation.accounts import AccountCredential, AccountStatusReporter, report_account_status


def test_report_account_status_spools_and_redacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CRAWLER_ACCOUNT_STATUS_SPOOL_DIR", str(tmp_path))
    event = report_account_status(company_code="ulike", platform_code="shopee", credential_key="shopee_ulike_id_local", status_code="COOKIE_EXPIRED", message="cookie=abc token=def", payload={"cookieString": "abc", "safe": "visible"})
    assert event["companyCode"] == "ulike"
    assert event["platformCode"] == "shopee"
    assert event["credentialKey"] == "shopee_ulike_id_local"
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["message"] == "cookie=***REDACTED*** token=***REDACTED***"
    assert payload["payload"]["cookieString"] == "***REDACTED***"
    assert payload["payload"]["safe"] == "visible"


def test_reporter_accepts_account_object(tmp_path: Path) -> None:
    reporter = AccountStatusReporter(company_code="ulike", run_id="100", task_id="200", spool_dir=tmp_path)
    account = AccountCredential(platform_code="oilchem", credential_key="oilchem_main", credential_name="Oilchem 主账号", slot="login", secret={"token": "abc"})
    event = reporter.report_success(account)
    assert event["companyCode"] == "ulike"
    assert event["runId"] == 100
    assert event["taskId"] == 200
    assert event["platformCode"] == "oilchem"
    assert event["credentialKey"] == "oilchem_main"
    assert event["slot"] == "login"
    assert event["statusCode"] == "LOGIN_OK"


def test_account_binding_modes_and_subject_affinity(tmp_path: Path) -> None:
    reporter = AccountStatusReporter(company_code="ulike", run_id="1", task_id="2", spool_dir=tmp_path)
    payload = {
        "accounts": {
            "login": {"mode": "fixed", "credential": {"platformCode": "demo", "credentialKey": "account_a", "auth": {"authorization": "Bearer secret"}}},
            "many": {"credentials": [{"platformCode": "demo", "credentialKey": "account_a"}, {"platformCode": "demo", "credentialKey": "account_b"}]},
            "rule": {"mode": "binding_rule", "platformCode": "demo", "rules": [{"conditions": {"brand": "ulike"}, "credentialKey": "account_c"}]},
        }
    }
    assert reporter.get("login", payload).credential_key == "account_a"
    assert reporter.auth(reporter.get("login", payload)).header_map()["Authorization"] == "Bearer secret"
    assert [a.credential_key for a in reporter.list("many", payload)] == ["account_a", "account_b"]
    assert reporter.resolve("rule", {"brand": "ulike"}, payload).credential_key == "account_c"
    with reporter.affinity("rule", "company", "c001", {"brand": "ulike", "companyName": "测试公司"}, payload) as account:
        assert account.credential_key == "account_c"
    files = list(tmp_path.glob("*.json"))
    assert any(json.loads(path.read_text(encoding="utf-8"))["eventType"] == "SUBJECT_BINDING" for path in files)


def test_external_affinity_writes_back_after_success(tmp_path: Path) -> None:
    reporter = AccountStatusReporter(company_code="ulike", spool_dir=tmp_path)
    writes: list[str] = []
    payload = {"accounts": {"queryAccount": {"mode": "fixed", "credential": {"platformCode": "demo", "credentialKey": "account_x"}}}}
    with reporter.external_affinity("queryAccount", "company", "c002", current_credential_key=None, on_bind_success=writes.append, subject_meta={"companyName": "外部公司"}, payload=payload) as account:
        assert account.credential_key == "account_x"
    assert writes == ["account_x"]
