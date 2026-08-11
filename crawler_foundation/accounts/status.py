from __future__ import annotations

import json
import os
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest

from crawler_foundation.core.files import ensure_dir
from crawler_foundation.core.json_utils import write_json
from crawler_foundation.core.logging import sanitize

SUCCESS_CODES = {"LOGIN_OK", "COOKIE_OK", "TOKEN_OK", "ACCOUNT_OK", "AUTH_OK", "SUBJECT_QUERY_OK", "TOKEN_REFRESH_OK"}
SUBJECT_SUCCESS_CODES = {"SUBJECT_QUERY_OK", "SUBJECT_BINDING_CREATED"}


class AccountError(RuntimeError):
    pass


class NoAvailableCredentialError(AccountError):
    pass


class BoundCredentialUnavailableError(AccountError):
    pass


class SubjectBindingConflictError(AccountError):
    pass


@dataclass(slots=True)
class AuthState:
    cookies: str = ""
    cookie_jar: list[dict[str, Any]] = field(default_factory=list)
    authorization: str = ""
    access_token: str = ""
    refresh_token: str = ""
    headers: dict[str, Any] = field(default_factory=dict)
    local_storage: dict[str, Any] = field(default_factory=dict)
    session_storage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "AuthState":
        data = dict(value or {})
        return cls(
            cookies=str(data.get("cookies") or data.get("cookieString") or data.get("cookie_string") or ""),
            cookie_jar=list(data.get("cookieJar") or data.get("cookie_jar") or []),
            authorization=str(data.get("authorization") or data.get("Authorization") or ""),
            access_token=str(data.get("accessToken") or data.get("access_token") or ""),
            refresh_token=str(data.get("refreshToken") or data.get("refresh_token") or ""),
            headers=dict(data.get("headers") or {}),
            local_storage=dict(data.get("localStorage") or data.get("local_storage") or {}),
            session_storage=dict(data.get("sessionStorage") or data.get("session_storage") or {}),
            raw=data,
        )

    def header_map(self) -> dict[str, str]:
        headers = {str(k): str(v) for k, v in self.headers.items() if v not in (None, "")}
        if self.authorization and "Authorization" not in headers:
            headers["Authorization"] = self.authorization
        elif self.access_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers


    def safe_dict(self) -> dict[str, Any]:
        return sanitize({
            "cookies": self.cookies, "cookieJar": self.cookie_jar, "authorization": self.authorization,
            "accessToken": self.access_token, "refreshToken": self.refresh_token, "headers": self.headers,
        })

_SENSITIVE_KEY = re.compile(r"(?:password|passwd|pwd|secret|token|cookie|authorization|access[_-]?key|private[_-]?key|email[_-]?token|phone|mobile)", re.I)
_SENSITIVE_TEXT = re.compile(r"(?i)(cookie|token|password|passwd|pwd|secret|authorization|email_token|phone_number|access_key)\s*[:=]\s*([^\s,;]+)")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_text(value: str, limit: int = 1000) -> str:
    return _SENSITIVE_TEXT.sub(lambda m: f"{m.group(1)}=***REDACTED***", str(value or ""))[:limit]


def _clean_payload(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    if key and _SENSITIVE_KEY.search(key):
        return "***REDACTED***"
    if depth > 8:
        return "<max-depth>"
    if isinstance(value, dict):
        return {str(k): _clean_payload(v, key=str(k), depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean_payload(v, depth=depth + 1) for v in value]
    if isinstance(value, str):
        return _clean_text(value, 500)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value or ""
    return default


@dataclass(slots=True)
class AccountCredential:
    platform_code: str
    credential_key: str
    credential_name: str = ""
    slot: str = ""
    public: dict[str, Any] = field(default_factory=dict)
    secret: dict[str, Any] = field(default_factory=dict)
    auth: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any], *, slot: str = "") -> "AccountCredential":
        platform = str(value.get("platformCode") or value.get("platform_code") or value.get("platform") or "")
        key = str(value.get("credentialKey") or value.get("credential_key") or value.get("credentialRef") or value.get("credential_ref") or value.get("key") or "")
        if key.startswith("credential:"):
            key = key.split(":", 1)[1]
        return cls(
            platform_code=platform,
            credential_key=key,
            credential_name=str(value.get("credentialName") or value.get("credential_name") or key),
            slot=slot or str(value.get("slot") or ""),
            public=dict(value.get("public") or {}),
            secret=dict(value.get("secret") or {}),
            auth=dict(value.get("auth") or {}),
            raw=dict(value),
        )

    @property
    def auth_state(self) -> AuthState:
        return AuthState.from_mapping(self.auth)

    def safe_dict(self) -> dict[str, Any]:
        return sanitize({
            "platformCode": self.platform_code,
            "credentialKey": self.credential_key,
            "credentialName": self.credential_name,
            "slot": self.slot,
            "public": self.public,
            "secret": self.secret,
            "auth": self.auth,
        })


class AccountStatusReporter:
    """Uniform Account Status Reporting Standard.

    The reporter never reads company Redis/Mongo/MySQL cookie stores. It only emits
    normalized status events keyed by company + platform + credentialKey. When the
    platform endpoint is unavailable it stores events in a local spool directory.
    """

    def __init__(self, *, company_id: str = "", company_code: str = "", run_id: str = "", task_id: str = "", agent_code: str = "", endpoint: str = "", token: str = "", spool_dir: str | Path = "runtime/spool/account-status", logger: Any = None, payload: dict[str, Any] | None = None, lease_acquire_endpoint: str = "", lease_release_endpoint: str = "") -> None:
        self.company_id = company_id
        self.company_code = company_code
        self.run_id = run_id
        self.task_id = task_id
        self.agent_code = agent_code
        self.endpoint = endpoint
        self.token = token
        self.spool_dir = ensure_dir(spool_dir)
        self.logger = logger
        self.payload = payload or {}
        self.lease_acquire_endpoint = lease_acquire_endpoint
        self.lease_release_endpoint = lease_release_endpoint

    @classmethod
    def from_context(cls, context: Any) -> "AccountStatusReporter":
        endpoint = _env_first("CRAWLER_ACCOUNT_STATUS_ENDPOINT", "ACCOUNT_STATUS_ENDPOINT")
        token = _env_first("CRAWLER_ACCOUNT_STATUS_TOKEN", "ACCOUNT_STATUS_TOKEN")
        company_code = _env_first("CRAWLER_COMPANY_CODE", "COMPANY_CODE", default=str(getattr(context, "extra", {}).get("companyCode", "") if getattr(context, "extra", None) else ""))
        agent_code = _env_first("CRAWLER_AGENT_CODE", "AGENT_CODE")
        spool = Path(getattr(context, "dirs").cache) / "account_status_spool"
        return cls(
            company_id=str(getattr(context, "company_id", "") or ""), company_code=company_code,
            run_id=str(getattr(context, "run_id", "") or ""), task_id=str(getattr(context, "task_id", "") or ""),
            agent_code=agent_code, endpoint=endpoint, token=token, spool_dir=spool, logger=getattr(context, "logger", None),
            payload=getattr(context, "payload", {}) if isinstance(getattr(context, "payload", {}), dict) else {},
            lease_acquire_endpoint=_env_first("CRAWLER_CREDENTIAL_LEASE_ACQUIRE_ENDPOINT", "CREDENTIAL_LEASE_ACQUIRE_ENDPOINT"),
            lease_release_endpoint=_env_first("CRAWLER_CREDENTIAL_LEASE_RELEASE_ENDPOINT", "CREDENTIAL_LEASE_RELEASE_ENDPOINT"),
        )

    def _slot_value(self, slot: str, payload: dict[str, Any] | None = None) -> Any:
        payload = self._payload(payload)
        accounts = payload.get("accounts") if isinstance(payload.get("accounts"), dict) else {}
        if not isinstance(accounts, dict) or slot not in accounts:
            raise KeyError(f"账号槽位不存在：{slot}")
        return accounts.get(slot)

    def _credential_from_slot_value(self, slot: str, value: Any) -> AccountCredential:
        if not isinstance(value, dict):
            raise KeyError(f"账号槽位不存在或不是对象：{slot}")
        mode = str(value.get("mode") or "").strip()
        if mode == "fixed" and isinstance(value.get("credential"), dict):
            return AccountCredential.from_mapping({**value["credential"], "slot": slot}, slot=slot)
        if isinstance(value.get("boundCredential"), dict):
            return AccountCredential.from_mapping({**value["boundCredential"], "slot": slot}, slot=slot)
        if isinstance(value.get("credential"), dict):
            return AccountCredential.from_mapping({**value["credential"], "slot": slot}, slot=slot)
        if isinstance(value.get("credentials"), list) and value["credentials"]:
            first = next((item for item in value["credentials"] if isinstance(item, dict)), None)
            if first:
                return AccountCredential.from_mapping({**first, "slot": slot}, slot=slot)
        if value.get("credentialKey") or value.get("credential_key") or value.get("key"):
            return AccountCredential.from_mapping({**value, "slot": slot}, slot=slot)
        raise NoAvailableCredentialError(f"账号槽位 {slot} 未解析到可用账号")

    def get(self, slot: str, payload: dict[str, Any] | None = None) -> AccountCredential:
        return self._credential_from_slot_value(slot, self._slot_value(slot, payload))

    def list(self, slot: str, payload: dict[str, Any] | None = None) -> list[AccountCredential]:
        value = self._slot_value(slot, payload)
        if isinstance(value, dict) and isinstance(value.get("credentials"), list):
            return [AccountCredential.from_mapping({**item, "slot": slot}, slot=slot) for item in value["credentials"] if isinstance(item, dict)]
        if isinstance(value, dict) and isinstance(value.get("credentialKeys"), list):
            platform = str(value.get("platformCode") or value.get("platform_code") or "")
            return [AccountCredential(platform_code=platform, credential_key=str(key), credential_name=str(key), slot=slot) for key in value["credentialKeys"] if str(key)]
        if isinstance(value, list):
            return [AccountCredential.from_mapping({**item, "slot": slot}, slot=slot) for item in value if isinstance(item, dict)]
        return [self._credential_from_slot_value(slot, value)]

    def _payload(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return payload if payload is not None else self.payload

    def auth(self, account: AccountCredential | dict[str, Any]) -> AuthState:
        if isinstance(account, dict):
            account = AccountCredential.from_mapping(account)
        return account.auth_state

    def mask(self, account: AccountCredential | dict[str, Any]) -> dict[str, Any]:
        if isinstance(account, dict):
            account = AccountCredential.from_mapping(account)
        return account.safe_dict()

    @contextmanager
    def lease(self, slot: str, payload: dict[str, Any] | None = None, lease_seconds: int = 1800):
        slot_value = self._slot_value(slot, payload)
        fallback_account = self._lease_fallback_account(slot, slot_value)
        lease_info = self._acquire_platform_lease(fallback_account, slot=slot, lease_seconds=lease_seconds, slot_value=slot_value)
        account = self._account_from_lease_info(lease_info, fallback=fallback_account, slot=slot)
        release_reason = "completed"
        try:
            yield account
            self.report_success(account, status_code="ACCOUNT_OK", message="账号租约使用完成")
        except Exception as exc:
            release_reason = "failed"
            self.report_failure(account, status_code="UNKNOWN_AUTH_ERROR", message=str(exc), severity="WARNING")
            raise
        finally:
            self._release_platform_lease(lease_info, reason=release_reason)


    def _lease_fallback_account(self, slot: str, value: Any) -> AccountCredential:
        try:
            return self._credential_from_slot_value(slot, value)
        except NoAvailableCredentialError:
            if isinstance(value, dict):
                mode = str(value.get("mode") or "")
                if mode in {"pool", "affinity_pool", "external_affinity_pool"}:
                    platform = str(value.get("platformCode") or value.get("platform_code") or "")
                    return AccountCredential(platform_code=platform, credential_key=str(value.get("credentialKey") or ""), slot=slot, raw=dict(value))
            raise

    def _account_from_lease_info(self, lease_info: dict[str, Any] | None, *, fallback: AccountCredential, slot: str) -> AccountCredential:
        if not isinstance(lease_info, dict):
            return fallback
        for key in ("credential", "account", "selectedCredential"):
            value = lease_info.get(key)
            if isinstance(value, dict):
                return AccountCredential.from_mapping({**value, "slot": slot}, slot=slot)
        lease = lease_info.get("lease") if isinstance(lease_info.get("lease"), dict) else {}
        if isinstance(lease, dict) and (lease.get("credentialKey") or lease.get("credential_key")):
            return AccountCredential.from_mapping({**fallback.raw, **lease, "slot": slot}, slot=slot)
        return fallback

    def resolve(self, slot: str, subject: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> AccountCredential:
        data = self._payload(payload)
        accounts = data.get("accounts") if isinstance(data.get("accounts"), dict) else {}
        value = accounts.get(slot) if isinstance(accounts, dict) else None
        if isinstance(value, dict) and value.get("mode") == "binding_rule":
            rules = value.get("rules") or []
            subject = subject or {}
            for rule in rules if isinstance(rules, list) else []:
                cond = rule.get("conditions") or {} if isinstance(rule, dict) else {}
                if all(str(subject.get(k, "")) == str(v) for k, v in cond.items()):
                    cred = rule.get("credential") or {"platformCode": value.get("platformCode"), "credentialKey": rule.get("credentialKey")}
                    return AccountCredential.from_mapping(cred, slot=slot)
        return self.get(slot, payload)

    @contextmanager
    def affinity(self, slot: str, subject_type: str, subject_key: str, subject_meta: dict[str, Any] | None = None, payload: dict[str, Any] | None = None):
        account = self.resolve(slot, subject={"subjectType": subject_type, "subjectKey": subject_key, **(subject_meta or {})}, payload=payload)
        try:
            yield account
            self.commit_subject_success(slot=slot, subject_type=subject_type, subject_key=subject_key, credential_key=account.credential_key, account=account, subject_meta=subject_meta)
        except Exception as exc:
            self.report_failure(account, status_code="SUBJECT_QUERY_FAILED", message=str(exc), slot=slot, payload={"subjectType": subject_type, "subjectKey": subject_key, "subjectMeta": subject_meta or {}}, severity="WARNING")
            raise

    @contextmanager
    def external_affinity(self, slot: str, subject_type: str, subject_key: str, current_credential_key: str | None = None, on_bind_success: Any = None, subject_meta: dict[str, Any] | None = None, payload: dict[str, Any] | None = None):
        data = self._payload(payload)
        if current_credential_key:
            accounts = data.get("accounts") if isinstance(data.get("accounts"), dict) else {}
            value = accounts.get(slot) if isinstance(accounts, dict) else {}
            platform = str(value.get("platformCode") or value.get("platform_code") or "") if isinstance(value, dict) else ""
            account = AccountCredential(platform_code=platform, credential_key=current_credential_key, credential_name=current_credential_key, slot=slot)
        else:
            account = self.resolve(slot, subject={"subjectType": subject_type, "subjectKey": subject_key, **(subject_meta or {})}, payload=payload)
        try:
            yield account
            if not current_credential_key and callable(on_bind_success):
                on_bind_success(account.credential_key)
            self.commit_subject_success(slot=slot, subject_type=subject_type, subject_key=subject_key, credential_key=account.credential_key, account=account, subject_meta=subject_meta, payload={"externalSubjectStore": True})
        except Exception as exc:
            self.report_failure(account, status_code="SUBJECT_QUERY_FAILED", message=str(exc), slot=slot, payload={"subjectType": subject_type, "subjectKey": subject_key, "externalSubjectStore": True}, severity="WARNING")
            raise

    def commit_subject_success(self, *, slot: str, subject_type: str, subject_key: str, credential_key: str, account: AccountCredential | None = None, subject_meta: dict[str, Any] | None = None, status_code: str = "SUBJECT_QUERY_OK", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        account = account or AccountCredential(platform_code="", credential_key=credential_key, slot=slot)
        event_payload = {"subjectMeta": subject_meta or {}, **(payload or {})}
        return self.report_status(account, credential_key=credential_key, status_code=status_code, severity="INFO", message="业务对象查询成功并提交账号亲和绑定", slot=slot, event_type="SUBJECT_BINDING", subject_type=subject_type, subject_key=subject_key, subject_name=str((subject_meta or {}).get("subjectName") or (subject_meta or {}).get("companyName") or ""), payload=event_payload)

    @contextmanager
    def refresh_lock(self, account: AccountCredential | dict[str, Any]):
        yield account

    def refresh_if_needed(self, account: AccountCredential, refresh_func: Any, *, should_refresh: bool = False) -> AccountCredential:
        if not should_refresh:
            return account
        refreshed = refresh_func(account)
        return refreshed if isinstance(refreshed, AccountCredential) else AccountCredential.from_mapping(refreshed, slot=account.slot)

    def report_success(self, account: AccountCredential | dict[str, Any] | None = None, *, platform_code: str = "", credential_key: str = "", credential_name: str = "", status_code: str = "LOGIN_OK", message: str = "账号使用成功", slot: str = "", payload: dict[str, Any] | None = None, subject_type: str = "", subject_key: str = "") -> dict[str, Any]:
        return self.report_status(account, platform_code=platform_code, credential_key=credential_key, credential_name=credential_name, status_code=status_code, severity="INFO", message=message, slot=slot, payload=payload, subject_type=subject_type, subject_key=subject_key)

    def report_failure(self, account: AccountCredential | dict[str, Any] | None = None, *, platform_code: str = "", credential_key: str = "", credential_name: str = "", status_code: str = "UNKNOWN_AUTH_ERROR", message: str = "账号使用失败", slot: str = "", payload: dict[str, Any] | None = None, severity: str = "WARNING", subject_type: str = "", subject_key: str = "", affects_credential: bool = True) -> dict[str, Any]:
        return self.report_status(account, platform_code=platform_code, credential_key=credential_key, credential_name=credential_name, status_code=status_code, severity=severity, message=message, slot=slot, payload=payload, subject_type=subject_type, subject_key=subject_key, affects_credential=affects_credential)

    def report_status(self, account: AccountCredential | dict[str, Any] | None = None, *, platform_code: str = "", credential_key: str = "", credential_name: str = "", status_code: str, severity: str = "INFO", source: str = "TASK_RUN", message: str = "", slot: str = "", payload: dict[str, Any] | None = None, event_uid: str | None = None, event_type: str = "STATUS", subject_type: str = "", subject_key: str = "", subject_name: str = "", affects_credential: bool = True) -> dict[str, Any]:
        if isinstance(account, dict):
            account = AccountCredential.from_mapping(account, slot=slot)
        if account:
            platform_code = platform_code or account.platform_code
            credential_key = credential_key or account.credential_key
            credential_name = credential_name or account.credential_name
            slot = slot or account.slot
        if not platform_code or not credential_key:
            raise ValueError("platform_code 和 credential_key 不能为空")
        event = {
            "companyId": int(self.company_id) if str(self.company_id).isdigit() else None,
            "companyCode": self.company_code or None,
            "platformCode": platform_code,
            "credentialKey": credential_key,
            "credentialName": credential_name,
            "runId": int(self.run_id) if str(self.run_id).isdigit() else None,
            "taskId": int(self.task_id) if str(self.task_id).isdigit() else None,
            "agentCode": self.agent_code,
            "slot": slot,
            "subjectType": subject_type,
            "subjectKey": subject_key,
            "subjectName": subject_name,
            "affectsCredential": affects_credential,
            "eventType": event_type,
            "statusCode": status_code.upper(),
            "severity": severity,
            "source": source,
            "message": _clean_text(message),
            "observedAt": _utc_iso(),
            "payload": _clean_payload(payload or {}),
            "eventUid": event_uid or f"acctevt_{uuid.uuid4().hex}",
        }
        if event["companyId"] is None:
            event.pop("companyId")
        if not event.get("companyCode"):
            event.pop("companyCode", None)
        for optional_key in ("subjectType", "subjectKey", "subjectName"):
            if not event.get(optional_key):
                event.pop(optional_key, None)
        self._emit_event_log(event)
        delivered = self._deliver(event)
        if not delivered:
            self._spool(event)
        return event

    def _emit_event_log(self, event: dict[str, Any]) -> None:
        if self.logger:
            try:
                self.logger.info("账号状态事件", event="account_status_reported", accountStatus=event)
                return
            except Exception:
                pass
        print(json.dumps({"crawler_account_status_event": event}, ensure_ascii=False, default=str), flush=True)

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urlrequest.Request(endpoint, data=body, method="POST", headers={"Content-Type": "application/json"})
        if self.token:
            req.add_header("Authorization", self.token if self.token.startswith(("Bearer ", "Agent ")) else f"Agent {self.token}")
        try:
            with urlrequest.urlopen(req, timeout=10) as response:  # noqa: S310 - platform endpoint is operator-provided
                raw = response.read().decode("utf-8", errors="ignore")
                data = json.loads(raw) if raw else {}
                return data if isinstance(data, dict) else {"data": data}
        except Exception as exc:
            if self.logger:
                try:
                    self.logger.warning("平台 API 调用失败", event="platform_api_failed", endpoint=endpoint, error=str(exc))
                except Exception:
                    pass
            return None

    def _acquire_platform_lease(self, account: AccountCredential, *, slot: str, lease_seconds: int, slot_value: Any = None) -> dict[str, Any] | None:
        if not self.lease_acquire_endpoint:
            return None
        slot_payload = slot_value if isinstance(slot_value, dict) else {}
        payload = {
            "companyId": int(self.company_id) if str(self.company_id).isdigit() else None,
            "companyCode": self.company_code or None,
            "platformCode": account.platform_code or str(slot_payload.get("platformCode") or slot_payload.get("platform_code") or ""),
            "credentialKey": account.credential_key,
            "slot": slot or account.slot,
            "mode": str(slot_payload.get("mode") or "fixed"),
            "selector": slot_payload.get("selector") or slot_payload.get("poolSelector") or {},
            "leasePolicy": slot_payload.get("leasePolicy") or {},
            "runId": int(self.run_id) if str(self.run_id).isdigit() else None,
            "taskId": int(self.task_id) if str(self.task_id).isdigit() else None,
            "agentCode": self.agent_code,
            "leaseSeconds": lease_seconds,
        }
        if payload["companyId"] is None:
            payload.pop("companyId")
        if not payload.get("companyCode"):
            payload.pop("companyCode", None)
        response = self._post_json(self.lease_acquire_endpoint, payload)
        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, dict):
            raise NoAvailableCredentialError("平台账号租约申请失败")
        return data

    def _release_platform_lease(self, lease_info: dict[str, Any] | None, *, reason: str) -> None:
        if not self.lease_release_endpoint or not isinstance(lease_info, dict):
            return
        lease = lease_info.get("lease") if isinstance(lease_info.get("lease"), dict) else {}
        payload = {"leaseId": lease.get("leaseId") or lease.get("lease_id"), "leaseToken": lease_info.get("leaseToken"), "reason": reason}
        self._post_json(self.lease_release_endpoint, {k: v for k, v in payload.items() if v not in (None, "")})

    def _deliver(self, event: dict[str, Any]) -> bool:
        if not self.endpoint:
            return False
        response = self._post_json(self.endpoint, event)
        if response is not None:
            return True
        if self.logger:
            try:
                self.logger.warning("账号状态事件上报失败，已写入本地 spool", event="account_status_spooled")
            except Exception:
                pass
        return False

    def _spool(self, event: dict[str, Any]) -> None:
        path = self.spool_dir / f"{event['eventUid']}.json"
        write_json(path, event)


def report_account_status(*, company_code: str = "", company_id: str | int = "", platform_code: str, credential_key: str, status_code: str, message: str = "", credential_name: str = "", severity: str = "INFO", source: str = "TASK_RUN", run_id: str | int = "", task_id: str | int = "", agent_code: str = "", slot: str = "", payload: dict[str, Any] | None = None, endpoint: str = "", token: str = "") -> dict[str, Any]:
    reporter = AccountStatusReporter(
        company_id=str(company_id or _env_first("CRAWLER_COMPANY_ID", "COMPANY_ID")),
        company_code=company_code or _env_first("CRAWLER_COMPANY_CODE", "COMPANY_CODE"),
        run_id=str(run_id or _env_first("CRAWLER_RUN_ID", "RUN_ID")),
        task_id=str(task_id or _env_first("CRAWLER_TASK_ID", "TASK_ID")),
        agent_code=agent_code or _env_first("CRAWLER_AGENT_CODE", "AGENT_CODE"),
        endpoint=endpoint or _env_first("CRAWLER_ACCOUNT_STATUS_ENDPOINT", "ACCOUNT_STATUS_ENDPOINT"),
        token=token or _env_first("CRAWLER_ACCOUNT_STATUS_TOKEN", "ACCOUNT_STATUS_TOKEN"),
        spool_dir=_env_first("CRAWLER_ACCOUNT_STATUS_SPOOL_DIR", "ACCOUNT_STATUS_SPOOL_DIR", default="runtime/spool/account-status"),
    )
    return reporter.report_status(platform_code=platform_code, credential_key=credential_key, credential_name=credential_name, status_code=status_code, severity=severity, source=source, message=message, slot=slot, payload=payload)
