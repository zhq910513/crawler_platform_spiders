from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TASK_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,95}$")
PLATFORM_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


@dataclass(frozen=True, slots=True)
class ScaffoldOptions:
    platform: str
    definition_key: str
    task_name: str
    task_group: str = ""
    browser: bool = False
    task_kind: str = "basic"  # basic/page/subject/api
    table_name: str = ""
    subject_type: str = "company"

    def normalized(self) -> "ScaffoldOptions":
        platform = self.platform.strip().lower()
        definition_key = self.definition_key.strip().lower()
        if not PLATFORM_RE.match(platform):
            raise RuntimeError("--platform 必须是小写字母、数字、下划线组合，且以小写字母开头")
        if not TASK_KEY_RE.match(definition_key):
            raise RuntimeError("--definition-key 必须是小写字母、数字、下划线组合，且以小写字母开头")
        task_kind = self.task_kind.strip().lower()
        if task_kind not in {"basic", "page", "subject", "api"}:
            raise RuntimeError("--task-kind 仅支持 basic/page/subject/api")
        return ScaffoldOptions(
            platform=platform,
            definition_key=definition_key,
            task_name=self.task_name.strip(),
            task_group=(self.task_group or platform).strip().lower(),
            browser=self.browser,
            task_kind=task_kind,
            table_name=(self.table_name or f"{definition_key}").strip().lower(),
            subject_type=(self.subject_type or "company").strip().lower(),
        )


def module_file(root: str | Path, options: ScaffoldOptions) -> Path:
    opts = options.normalized()
    short_name = opts.definition_key
    prefix = opts.platform + "_"
    if short_name.startswith(prefix):
        short_name = short_name[len(prefix):]
    return Path(root) / "spiders" / opts.platform / f"{short_name}.py"


def _class_name(definition_key: str) -> str:
    return "".join(part.capitalize() for part in definition_key.split("_") if part) + "Task"


def _common_definition(opts: ScaffoldOptions) -> str:
    browser = "True" if opts.browser else "False"
    shm = 512 if opts.browser else 64
    creds = (
        '[{"slot": "api", "label": "API账号", "platformCode": "' + opts.platform + '", "credentialType": "API_TOKEN", "supportedModes": ["fixed", "pool"], "required": True}]'
        if opts.task_kind == "api"
        else '[{"slot": "login", "label": "登录账号", "platformCode": "' + opts.platform + '", "credentialType": "WEB_COOKIE", "supportedModes": ["fixed", "pool"], "required": False}]'
    )
    if opts.task_kind == "subject":
        creds = '[{"slot": "queryAccount", "label": "查询账号", "platformCode": "' + opts.platform + '", "credentialType": "WEB_COOKIE", "supportedModes": ["affinity_pool", "external_affinity_pool"], "required": True, "affinity": {"subjectType": "' + opts.subject_type + '", "bindingPolicy": "BIND_ON_SUCCESS", "rebindingPolicy": "MANUAL_ONLY"}}]'
    return f'''TASK_DEFINITION = {{
    "definitionKey": "{opts.definition_key}",
    "taskName": "{opts.task_name.replace('"', '\\"')}",
    "platformCode": "{opts.platform}",
    "entryModule": "spiders.{opts.platform}.{module_file_name(opts)}",
    "entryFunction": "run",
    "contractVersion": "1",
    "defaultParams": {{"batchSize": 200}},
    "suggestedCron": "",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "resourceRequirements": {{}},
    "requiredCapabilities": {{"browser": {browser}}},
    "runtimeMode": "SHARED_ENV_ISOLATED",
    "taskGroup": "{opts.task_group}",
    "taskMaxConcurrency": 1,
    "groupMaxConcurrency": 4,
    "exclusiveMode": False,
    "ioClass": "NORMAL",
    "shmSizeMb": {shm},
    "logLimitMb": 20,
    "resourceLocks": [],
    "secretRefs": [],
    "requiredConfigs": [{{"slot": "mysql_main", "type": "MYSQL", "required": True}}],
    "requiredCredentials": {creds},
    "outputTables": [{{"slot": "detailTable", "defaultName": "{opts.table_name}", "writeMethod": "replace"}}],
    "allowOfflineRun": False,
    "offlinePolicy": {{}},
}}
'''


def module_file_name(opts: ScaffoldOptions) -> str:
    path = module_file(Path("."), opts).with_suffix("")
    return path.name


def render_task_template(options: ScaffoldOptions) -> str:
    opts = options.normalized()
    cls = _class_name(opts.definition_key)
    definition = _common_definition(opts)
    if opts.task_kind == "page":
        body = f'''from __future__ import annotations

from typing import Any

from crawler_foundation.core.result import TaskResult
from spiders.common.standard import StandardPageTask


{definition}


class {cls}(StandardPageTask):
    platform_code = "{opts.platform}"
    default_table_name = "{opts.table_name}"

    def request_page(self, page: int) -> Any:
        # TODO: 调用平台接口或页面请求，失败时抛标准异常。
        return {{"list": [], "hasNext": False, "page": page}}

    def parse_page(self, response: Any, page: int) -> tuple[list[dict[str, Any]], bool]:
        rows = response.get("list", []) if isinstance(response, dict) else []
        has_next = bool(response.get("hasNext")) if isinstance(response, dict) else False
        return rows, has_next


def run(context, **kwargs) -> TaskResult:
    return {cls}(context).run()
'''
    elif opts.task_kind == "subject":
        body = f'''from __future__ import annotations

from typing import Any

from crawler_foundation.accounts import AccountCredential
from crawler_foundation.core.result import TaskResult
from spiders.common.standard import StandardSubjectTask


{definition}


class {cls}(StandardSubjectTask):
    platform_code = "{opts.platform}"
    subject_type = "{opts.subject_type}"
    account_slot = "queryAccount"
    default_table_name = "{opts.table_name}"

    def iter_subjects(self):
        # TODO: 从业务缓存、数据库或任务参数中取待处理对象。
        return self.params.get("subjects") or []

    def get_subject_key(self, subject: dict[str, Any]) -> str:
        return str(subject.get("subjectKey") or subject.get("company_id") or subject.get("id") or "")

    def query_subject(self, subject: dict[str, Any], account: AccountCredential) -> dict[str, Any] | None:
        # TODO: 使用 account 查询业务对象，成功后公共层会提交对象账号亲和绑定。
        return {{**subject, "credential_key": account.credential_key}}


def run(context, **kwargs) -> TaskResult:
    return {cls}(context).run()
'''
    elif opts.task_kind == "api":
        body = f'''from __future__ import annotations

from crawler_foundation.core.result import TaskResult
from spiders.common.standard import StandardApiBase


{definition}


class {cls}(StandardApiBase):
    platform_code = "{opts.platform}"

    def run(self) -> TaskResult:
        account = self.load_api_account("api")
        self.logger.info("API任务开始", event="api_task_started", account=self.context.accounts.mask(account))
        # TODO: 调用 API，请在 raise_for_api_error 中统一映射 token/sign/quota 错误。
        return TaskResult.success("API任务执行成功")


def run(context, **kwargs) -> TaskResult:
    return {cls}(context).run()
'''
    else:
        body = f'''from __future__ import annotations

from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task


{definition}


@platform_task()
def run(context, **kwargs) -> TaskResult:
    context.logger.info("任务开始", event="business_started", params=kwargs)
    # TODO: 推荐后续改为 StandardPageTask / StandardSubjectTask / StandardApiBase。
    return TaskResult.success("任务模板执行成功", data={{"kwargs": kwargs}})
'''
    return body
