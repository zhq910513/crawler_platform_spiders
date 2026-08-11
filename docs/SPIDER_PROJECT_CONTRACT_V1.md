# 爬虫项目标准契约 v1（crawler_platform_spiders 1.0.13）

## 目标

本标准让爬虫项目做到：平台可发现、可调度、可配置、可分配账号、可上报账号状态、可追踪对象账号绑定，同时避免账号、Cookie、Token、数据库连接硬编码。

## 目录规范

最小结构：

```text
/spiders/{platform_code}/base.py
/spiders/{platform_code}/{task_code}.py
```

复杂平台允许扩展：

```text
/spiders/{platform_code}/auth.py
/spiders/{platform_code}/client.py
/spiders/{platform_code}/parsers.py
/spiders/{platform_code}/tasks/{task_code}.py
```

但平台入口必须固定为：

```python
def run(context):
    ...
```

## TASK_DEFINITION 必填契约

业务模块必须声明静态字面量 `TASK_DEFINITION`：

```python
TASK_DEFINITION = {
    "definitionKey": "company_info_query",
    "taskName": "公司信息查询",
    "platformCode": "a_platform",
    "entryModule": "spiders.a_platform.company_info_query",
    "entryFunction": "run",
    "requiredConfigs": [
        {"slot": "mysql_main", "type": "MYSQL", "required": True}
    ],
    "requiredCredentials": [
        {
            "slot": "queryAccount",
            "platformCode": "a_platform",
            "credentialType": "WEB_COOKIE",
            "supportedModes": ["fixed", "pool", "affinity_pool", "external_affinity_pool"],
            "required": True
        }
    ],
    "outputTables": [
        {"slot": "companyInfoTable", "defaultName": "company_info", "writeMethod": "replace"}
    ],
    "allowOfflineRun": False,
}
```

`sync_sch.py` 会自动补齐 `platformCode`、`requiredConfigs`、`requiredCredentials`、`outputTables`、`contractVersion`，并输出给爬虫平台。

## 公共账号方法

后续业务代码只使用 `context.accounts`：

```python
account = context.accounts.get("login")
accounts = context.accounts.list("shopAccounts")
with context.accounts.lease("worker") as account:
    ...
account = context.accounts.resolve("login", subject=shop)
with context.accounts.affinity("queryAccount", "company", company_id) as account:
    ...
with context.accounts.external_affinity("queryAccount", "company", company_id, current_credential_key=company.get("credential_key"), on_bind_success=write_back) as account:
    ...
```

账号状态上报：

```python
context.accounts.report_success(account, status_code="LOGIN_OK")
context.accounts.report_failure(account, status_code="COOKIE_EXPIRED", message="请求命中登录页")
```

## 对象账号亲和绑定

适合“第一次查询成功后，后续必须使用同一个账号”的场景：

```python
with context.accounts.affinity(
    slot="queryAccount",
    subject_type="company",
    subject_key=company["company_id"],
    subject_meta={"companyName": company["company_name"]},
) as account:
    client = APlatformBase.from_account(context, account)
    data = client.query_company(company)
```

兼容旧业务缓存字段：

```python
with context.accounts.external_affinity(
    slot="queryAccount",
    subject_type="company",
    subject_key=company["company_id"],
    current_credential_key=company.get("credential_key"),
    on_bind_success=lambda credential_key: update_company_credential_key(company["company_id"], credential_key),
) as account:
    ...
```

## 标准基类

1.0.13 新增：

- `StandardPlatformBase`
- `StandardWebBase`
- `StandardApiBase`
- `StandardSubjectQueryTask`

Web 平台继承 `StandardWebBase`，API 平台继承 `StandardApiBase`，大量对象查询任务继承 `StandardSubjectQueryTask`。

## 禁止事项

- 禁止在代码中硬编码账号、Cookie、Token、API key、数据库密码。
- 禁止业务代码直接高频访问平台状态 API 判断账号是否存活。
- 禁止状态事件上报明文 Cookie、Token、密码、邮箱 token、手机号。
- 禁止未查询成功就写入对象账号绑定。
- 禁止对象已绑定账号不可用时自动换绑，除非平台任务策略明确允许。
