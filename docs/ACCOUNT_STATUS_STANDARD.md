# 账号状态上报规范（1.0.13）

本规范用于解决多公司、多平台、多账号、多缓存库场景下的账号状态一致性问题。

## 标准定位键

所有账号状态事件必须使用以下键定位账号：

```text
companyCode/companyId + platformCode + credentialKey
```

`credentialKey` 是业务稳定唯一编码，不要求等于真实用户名、邮箱、手机号或店铺 ID。

## 设计边界

公共组件只负责上报账号状态事件，不负责读取公司账号缓存库：

- 不读取 Redis Cookie。
- 不读取 Mongo Cookie。
- 不读取 MySQL 账号表。
- 不判断账号字段结构。
- 不保存账号明文。

真实凭证可以存放在平台 Vault、公司 Redis、Mongo、MySQL、外部旧系统或人工临时 Cookie 中；状态统一回到爬虫平台账号状态中心。

## 推荐状态码

成功类：`LOGIN_OK`、`COOKIE_OK`、`TOKEN_OK`、`ACCOUNT_OK`。

登录态异常：`COOKIE_EXPIRED`、`COOKIE_INVALID`、`TOKEN_EXPIRED`、`TOKEN_INVALID`、`LOGIN_FAILED`。

人工接管：`CAPTCHA_REQUIRED`、`EMAIL_VERIFY_REQUIRED`、`PHONE_VERIFY_REQUIRED`、`TWO_FACTOR_REQUIRED`。

平台限制：`RATE_LIMITED`、`QUOTA_LIMITED`、`ACCOUNT_DISABLED_BY_PLATFORM`、`ACCOUNT_LOCKED_BY_PLATFORM`。

环境异常：`NETWORK_ERROR`、`PLATFORM_5XX`、`PLATFORM_MAINTENANCE`。

## 新项目调用

```python
account = context.accounts.get("login", context.payload)
context.accounts.report_success(account, status_code="LOGIN_OK")
context.accounts.report_failure(account, status_code="COOKIE_EXPIRED", message="返回登录页")
```

也可以不依赖账号对象：

```python
context.accounts.report_success(platform_code="shopee", credential_key="shopee_ulike_id_local")
```

## 旧项目调用

```python
from crawler_foundation.accounts import report_account_status

report_account_status(
    company_code="ulike",
    platform_code="shopee",
    credential_key="shopee_ulike_id_local",
    status_code="LOGIN_OK",
)
```

## 脱敏要求

状态事件中禁止包含：Cookie、Token、密码、passwordHash、emailToken、手机号、完整请求头、完整响应体。公共组件会做基础脱敏，但业务代码仍不应主动传入敏感内容。
