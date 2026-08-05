# crawler_platform_spiders 1.0.4

## 版本定位

Oilchem 登录链路 HAR 复盘整改版。

## 本次变更

- 根据无痕浏览器 HAR 重新梳理 Oilchem 登录流程。
- `spiders/oilchem/base.py` 支持 `username + password + NECaptchaValidate` 表单登录。
- 保留并强化 `token` / `cookieString` 登录态校验模式。
- 表单登录按浏览器流程提交 `passport.oilchem.net/member/login/login`。
- 密码字段自动做 MD5；如果传入 32 位 MD5，则不会二次加密。
- 支持 `captchaValidate` / `NECaptchaValidate` / `vcode` 多种入参别名。
- 登录成功后从 `Set-Cookie` / session cookie 中提取 `_member_user_tonken_`。
- 登录后用 `dc.oilchem.net/ndc/common/getUserId` 做二次校验。
- Redis/Mongo 缓存从只存 token 增强为保存安全 cookie 集合；不会保存 `_pass`。
- `oilchem_login_check` 任务默认参数补齐 `password`、`captchaValidate`、`captchaId`、`target`。
- 新增 Oilchem 登录表单单元测试与模拟登录成功测试。

## 仍需外部提供

- 网易易盾 `NECaptchaValidate`。本基类不在纯 requests 里伪造或绕过验证码，只接收浏览器、人工或合规打码服务已经返回的 validate。

## 建议命令

```bash
python scripts/sync_sch.py --check && python scripts/validate_tasks.py && python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins scripts && pytest -q
```
