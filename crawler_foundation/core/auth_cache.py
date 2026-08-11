from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from crawler_foundation.accounts import AuthState
from crawler_foundation.core.logging import sanitize


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fingerprint_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(slots=True)
class AuthCacheRecord:
    """Standard login/auth cache record used by Web and API spiders.

    It is safe to store this object in Redis/Mongo/MySQL after project-level
    encryption rules are applied.  Use ``safe_dict`` for logs and diagnostics.
    """

    company_code: str
    platform_code: str
    credential_key: str
    auth: AuthState = field(default_factory=AuthState)
    auth_source: str = "TASK_RUN"
    health_status: str = "UNKNOWN"
    login_status: str = "NO_AUTH"
    status_code: str = "UNKNOWN"
    expires_at: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: str = "1.0"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "AuthCacheRecord":
        status = value.get("status") if isinstance(value.get("status"), dict) else {}
        return cls(
            schema_version=str(value.get("schema_version") or value.get("schemaVersion") or "1.0"),
            company_code=str(value.get("company_code") or value.get("companyCode") or ""),
            platform_code=str(value.get("platform_code") or value.get("platformCode") or ""),
            credential_key=str(value.get("credential_key") or value.get("credentialKey") or value.get("hash_key") or ""),
            auth=AuthState.from_mapping(value.get("auth") if isinstance(value.get("auth"), dict) else {}),
            auth_source=str(value.get("auth_source") or value.get("authSource") or "TASK_RUN"),
            health_status=str(status.get("health_status") or status.get("healthStatus") or value.get("healthStatus") or "UNKNOWN"),
            login_status=str(status.get("login_status") or status.get("loginStatus") or value.get("loginStatus") or "NO_AUTH"),
            status_code=str(status.get("status_code") or status.get("statusCode") or value.get("statusCode") or "UNKNOWN"),
            expires_at=value.get("expires_at") or value.get("expiresAt"),
            updated_at=str(value.get("updated_at") or value.get("updatedAt") or utc_now_iso()),
            extra=dict(value.get("extra") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        auth_payload = {
            "cookies": self.auth.cookies,
            "cookieJar": self.auth.cookie_jar,
            "authorization": self.auth.authorization,
            "accessToken": self.auth.access_token,
            "refreshToken": self.auth.refresh_token,
            "headers": self.auth.headers,
            "localStorage": self.auth.local_storage,
            "sessionStorage": self.auth.session_storage,
        }
        payload = {
            "schema_version": self.schema_version,
            "company_code": self.company_code,
            "platform_code": self.platform_code,
            "credential_key": self.credential_key,
            "auth": auth_payload,
            "auth_source": self.auth_source,
            "status": {
                "health_status": self.health_status,
                "login_status": self.login_status,
                "status_code": self.status_code,
            },
            "expires_at": self.expires_at,
            "updated_at": self.updated_at,
            "fingerprint": fingerprint_payload(auth_payload),
        }
        if self.extra:
            payload["extra"] = self.extra
        return payload

    def safe_dict(self) -> dict[str, Any]:
        return sanitize(self.to_dict())
