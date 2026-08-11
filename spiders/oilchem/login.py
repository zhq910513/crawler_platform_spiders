# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from crawler_foundation.core.context import TaskContext
from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task
from spiders.oilchem.base import OilchemAccount, OilchemBase

TASK_DEFINITION = {
    "definitionKey": "oilchem_login_check",
    "taskName": "隆众资讯登录校验",
    "defaultParams": {
        "username": "",
        "password": "",
        "token": "",
        "cookieString": "",
        "cookieSecretRef": "",
        "credentialKey": "oilchem_main",
        "captchaValidate": "",
        "captchaId": "a17cc715e78a4afc8c43cd85da9d7254",
        "target": "https://dc.oilchem.net/page/#/index",
        "check": True,
        "persist": True,
    },
    "suggestedCron": "",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "resourceRequirements": {},
    "requiredCapabilities": {"browser": False},
    "runtimeMode": "SHARED_ENV_ISOLATED",
    "taskGroup": "oilchem",
    "taskMaxConcurrency": 1,
    "groupMaxConcurrency": 2,
    "exclusiveMode": False,
    "ioClass": "NORMAL",
    "shmSizeMb": 64,
    "logLimitMb": 20,
    "resourceLocks": [],
    "secretRefs": ["oilchem_account"],
    "allowOfflineRun": False,
    "offlinePolicy": {"maxOfflineHours": 0, "reason": "登录校验默认不离线执行，避免 cookie 失效时重复请求。"},
}


@platform_task()
def run(
    context: TaskContext,
    *,
    username: str = "",
    password: str = "",
    token: str = "",
    cookieString: str = "",
    cookie_string: str = "",
    cookieSecretRef: str = "",
    cookie_secret_ref: str = "",
    credentialKey: str = "",
    credential_key: str = "",
    captchaValidate: str = "",
    captcha_validate: str = "",
    NECaptchaValidate: str = "",
    neCaptchaValidate: str = "",
    captchaId: str = "",
    captcha_id: str = "",
    vcode: str = "",
    target: str = "",
    targetUrl: str = "",
    account: dict[str, Any] | None = None,
    check: bool = True,
    persist: bool = True,
) -> TaskResult:
    payload = dict(context.payload)
    if account:
        payload["account"] = account
    oilchem_account = OilchemAccount.from_payload(
        payload,
        username=username,
        password=password,
        token=token,
        cookieString=cookieString or cookie_string,
        cookieSecretRef=cookieSecretRef or cookie_secret_ref,
        captchaValidate=captchaValidate or captcha_validate or NECaptchaValidate or neCaptchaValidate or vcode,
        captchaId=captchaId or captcha_id,
        target=target or targetUrl,
    )
    spider = OilchemBase(context, account=oilchem_account)
    try:
        data = spider.login(oilchem_account, check=bool(check), persist=bool(persist))
        key = credentialKey or credential_key or oilchem_account.username or "oilchem_main"
        context.accounts.report_success(platform_code="oilchem", credential_key=key, credential_name=oilchem_account.username or key, status_code="LOGIN_OK", message="oilchem 登录态有效", slot="login")
        return TaskResult.success("oilchem 登录校验成功", metrics={"checked": int(bool(check)), "persisted": int(bool(persist))}, data=data)
    except Exception as exc:
        key = credentialKey or credential_key or oilchem_account.username or "oilchem_main"
        context.accounts.report_failure(platform_code="oilchem", credential_key=key, credential_name=oilchem_account.username or key, status_code="LOGIN_FAILED", message=str(exc), slot="login")
        raise
    finally:
        spider.close()
