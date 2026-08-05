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
        captchaValidate=captchaValidate or captcha_validate or NECaptchaValidate or neCaptchaValidate or vcode,
        captchaId=captchaId or captcha_id,
        target=target or targetUrl,
    )
    spider = OilchemBase(context, account=oilchem_account)
    try:
        data = spider.login(oilchem_account, check=bool(check), persist=bool(persist))
        return TaskResult.success("oilchem 登录校验成功", metrics={"checked": int(bool(check)), "persisted": int(bool(persist))}, data=data)
    finally:
        spider.close()
