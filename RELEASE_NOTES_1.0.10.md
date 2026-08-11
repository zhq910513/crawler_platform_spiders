# crawler_platform_spiders 1.0.10 发布说明

本版本配合 crawler_platform 1.0.17，落地“账号状态上报规范”的爬虫项目侧公共组件。

## 核心变化

- 新增 `crawler_foundation.accounts` 公共组件。
- 新增 `AccountStatusReporter`，统一通过 `companyId/companyCode + platformCode + credentialKey` 上报账号状态。
- 新增旧项目兼容函数 `report_account_status(...)`。
- `TaskContext` 新增 `context.accounts`。
- 账号状态事件默认脱敏并写入本地 spool；配置平台端点后可直接 HTTP 上报。
- Oilchem 登录校验示例在登录成功/失败时上报账号状态事件。
- 明确公共组件不访问 Redis/Mongo/MySQL/Cookie 缓存库，只负责标准状态事件上报。

## 标准调用

```python
context.accounts.report_success(platform_code="shopee", credential_key="shopee_ulike_id_local", status_code="LOGIN_OK")
context.accounts.report_failure(platform_code="shopee", credential_key="shopee_ulike_id_local", status_code="COOKIE_EXPIRED", message="登录态已过期")
```

旧项目兼容：

```python
from crawler_foundation.accounts import report_account_status

report_account_status(company_code="ulike", platform_code="shopee", credential_key="shopee_ulike_id_local", status_code="LOGIN_OK")
```
