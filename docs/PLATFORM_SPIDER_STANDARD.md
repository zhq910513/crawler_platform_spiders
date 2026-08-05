# 平台爬虫代码规范

## 目录规范

每个平台一个目录：

```text
spiders/<platform>/
  __init__.py
  base.py
  <business_name>.py
```

例如 Oilchem：

```text
spiders/oilchem/
  __init__.py
  base.py
  login.py
```

## base.py 职责

`base.py` 只放平台通用能力：

- 账号参数模型。
- 登录、token/cookie 校验。
- session 创建。
- headers 生成。
- Redis/Mongo cookie/token 缓存。
- 平台通用 GET/POST JSON 请求。
- 平台通用异常转换。

`base.py` 禁止写具体业务解析和业务表入库逻辑。

## 业务名.py 职责

`业务名.py` 只放具体业务：

- 声明静态 `TASK_DEFINITION`。
- 接收账号信息和业务参数。
- 调用 `base.py` 完成登录与请求。
- 解析业务数据。
- 调用 `plugins.db.mysql.MySQLClient.insert_rows()` 等 DB 基类方法入库。
- 业务代码自己决定入库表名，但必须传安全表名和字段名。

业务模块禁止硬编码账号、密码、token、cookie。

## 账号传参规范

优先使用任务参数：

```json
{
  "account": {
    "username": "账号",
    "password": "可选",
    "token": "可选",
    "cookieString": "可选",
    "captchaValidate": "验证码平台或浏览器返回的校验串，可选"
  }
}
```

也兼容顶层参数：

```json
{"username":"账号","token":"..."}
```

本地调试可用环境变量兜底：

```text
OILCHEM_USERNAME
OILCHEM_PASSWORD
OILCHEM_TOKEN
OILCHEM_COOKIE_STRING
```

## 任务定义同步

新增或修改任务后执行：

```bash
python scripts/sync_sch.py --write && python scripts/validate_tasks.py
```

`sch.py` 不手工改，由脚本从 `spiders/` 下的静态 `TASK_DEFINITION` 自动生成。


## Oilchem 登录补充规范

Oilchem 的账号密码登录链路包含网易易盾校验。业务任务可以使用三种登录态来源：

1. `token`：直接校验并使用 `_member_user_tonken_`。
2. `cookieString`：从完整 cookie 中提取 `_member_user_tonken_`。
3. `username + password + captchaValidate`：按浏览器表单链路登录。

`password` 可以传明文，也可以传 32 位 MD5。基类会自动避免二次 MD5。

`captchaValidate` 不允许写死在代码中，应从平台任务参数、密钥配置、浏览器登录辅助流程或合规打码服务传入。
