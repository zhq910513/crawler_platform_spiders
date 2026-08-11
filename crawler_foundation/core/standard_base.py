from __future__ import annotations

from typing import Any, Iterable

from crawler_foundation.accounts import AccountCredential, AuthState
from crawler_foundation.core.context import TaskContext
from crawler_foundation.core.batch import BatchWriter, normalize_rows
from crawler_foundation.core.exceptions import AccountAuthError, AccountRateLimitedError, AccountVerifyRequiredError, RequestFatalError, RequestRetryableError, StorageError


class StandardPlatformBase:
    """Spider Project Standard Contract v1 base class.

    It keeps business code thin: context/config/accounts/logger are initialized here;
    concrete tasks only implement run/request/parse/save.
    """

    platform_code = ""
    default_mysql_slot = "mysql_main"

    def __init__(self, context: TaskContext) -> None:
        self.context = context
        self.params = context.payload
        self.logger = context.logger.bind(platform=self.platform_code or self.__class__.__name__)
        self.db = self._init_db()

    def _init_db(self) -> Any:
        config = getattr(self.context, "config", None)
        if config and hasattr(config, "mysql"):
            return config.mysql(self.default_mysql_slot)
        return None

    def output_table(self, slot: str = "detailTable", default: str = "") -> str:
        return str(self.params.get(slot) or self.params.get("tableName") or default or "")

    def save_rows(self, table_name: str, rows: list[dict[str, Any]], *, method: str = "replace") -> None:
        rows = normalize_rows(rows)
        if not rows:
            return
        if not self.db or not hasattr(self.db, "batch_insert_replace"):
            raise StorageError("数据库客户端未初始化或不支持 batch_insert_replace")
        self.db.batch_insert_replace(table_name, rows, method=method)

    def batch_writer(self, table_name: str, *, method: str = "replace", batch_size: int = 200) -> BatchWriter:
        return BatchWriter(lambda rows: self.save_rows(table_name, rows, method=method), batch_size=batch_size)

    def report_account_failure(self, account: AccountCredential, status_code: str, message: str, *, slot: str = "", subject_type: str = "", subject_key: str = "", affects_credential: bool = True) -> None:
        self.context.accounts.report_failure(account, status_code=status_code, message=message, slot=slot or account.slot, subject_type=subject_type, subject_key=subject_key, affects_credential=affects_credential)

    def report_account_success(self, account: AccountCredential, status_code: str = "LOGIN_OK", message: str = "账号使用成功", *, slot: str = "", subject_type: str = "", subject_key: str = "") -> None:
        self.context.accounts.report_success(account, status_code=status_code, message=message, slot=slot or account.slot, subject_type=subject_type, subject_key=subject_key)


class StandardWebBase(StandardPlatformBase):
    default_account_slot = "login"

    def load_account(self, slot: str | None = None) -> AccountCredential:
        self.account = self.context.accounts.get(slot or self.default_account_slot, self.context.payload)
        self.auth = self.context.accounts.auth(self.account)
        return self.account

    def auth_headers(self, auth: AuthState | None = None) -> dict[str, str]:
        return (auth or getattr(self, "auth", AuthState())).header_map()

    def raise_for_auth_or_request_error(self, response: Any, *, account: AccountCredential | None = None) -> None:
        status_code = int(getattr(response, "status_code", 0) or 0)
        text = str(getattr(response, "text", "") or "")[:500]
        account = account or getattr(self, "account", None)
        if status_code in {401, 403}:
            if account:
                self.report_account_failure(account, "COOKIE_EXPIRED", f"HTTP {status_code} 登录态失效")
            raise AccountAuthError(f"HTTP {status_code} 登录态失效")
        if status_code == 429:
            if account:
                self.report_account_failure(account, "RATE_LIMITED", "账号或平台被限流")
            raise AccountRateLimitedError("账号或平台被限流")
        if status_code >= 500:
            if account:
                self.context.accounts.report_failure(account, status_code="PLATFORM_5XX", message=f"平台 5xx：{status_code}", affects_credential=False)
            raise RequestRetryableError(f"平台 5xx：{status_code}")
        if 400 <= status_code < 500:
            raise RequestFatalError(f"HTTP {status_code}: {text}")


class StandardApiBase(StandardPlatformBase):
    default_account_slot = "api"

    def load_api_account(self, slot: str | None = None) -> AccountCredential:
        self.account = self.context.accounts.get(slot or self.default_account_slot, self.context.payload)
        self.auth = self.context.accounts.auth(self.account)
        return self.account

    def ensure_token_valid(self, account: AccountCredential | None = None) -> AccountCredential:
        return account or getattr(self, "account")

    def raise_for_api_error(self, data: dict[str, Any], *, account: AccountCredential | None = None) -> None:
        account = account or getattr(self, "account", None)
        code = str(data.get("code") or data.get("error") or "").upper()
        message = str(data.get("message") or data.get("msg") or code)
        if code in {"TOKEN_EXPIRED", "ACCESS_TOKEN_EXPIRED"}:
            if account:
                self.report_account_failure(account, "TOKEN_EXPIRED", message)
            raise AccountAuthError(message)
        if code in {"SIGNATURE_INVALID", "APP_SECRET_INVALID", "APP_KEY_INVALID"}:
            if account:
                self.report_account_failure(account, code, message)
            raise AccountAuthError(message)
        if code in {"RATE_LIMITED", "API_QUOTA_LIMITED"}:
            if account:
                self.report_account_failure(account, code, message)
            raise AccountRateLimitedError(message)


class StandardSubjectQueryTask(StandardPlatformBase):
    subject_type = "subject"
    account_slot = "queryAccount"

    def get_subject_key(self, subject: dict[str, Any]) -> str:
        return str(subject.get("subjectKey") or subject.get("id") or subject.get("company_id") or subject.get("companyId") or "")

    def get_subject_meta(self, subject: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in subject.items() if k not in {"cookie", "token", "password"}}

    def query_subject(self, subject: dict[str, Any], account: AccountCredential) -> dict[str, Any]:
        raise NotImplementedError

    def run_subjects(self, subjects: Iterable[dict[str, Any]]):
        for subject in subjects:
            subject_key = self.get_subject_key(subject)
            with self.context.accounts.affinity(self.account_slot, self.subject_type, subject_key, self.get_subject_meta(subject), self.context.payload) as account:
                yield self.query_subject(subject, account)
