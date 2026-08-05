# Oilchem 登录 HAR 复盘说明（1.0.4）

## 结论

无痕浏览器 HAR 表明，Oilchem 登录链路不是单纯 token 校验，账号密码登录会经过 `passport.oilchem.net/member/login/login` 表单提交，并依赖网易易盾返回的 `NECaptchaValidate`。

## 关键请求

1. 访问首页：

```text
GET https://dc.oilchem.net/page/
```

2. 登录前 token 检查：

```text
GET https://passport.oilchem.net/member/login/checkToken
```

3. 网易易盾校验：

```text
c.dun.163.com/api/v3/get
c.dun.163.com/api/v3/check
```

`check` 成功后会得到 `validate` 字段。

4. 表单登录：

```text
POST https://passport.oilchem.net/member/login/login
Content-Type: application/x-www-form-urlencoded
```

表单字段：

```text
username
password              # 32位 MD5
agree=on
NECaptchaValidate    # 网易易盾 validate
target
errorPaw             # HAR 中与 MD5 password 一致并带括号
captchaId
a17cc715e78a4afc8c43cd85da9d7254
vcode                # 与 NECaptchaValidate 一致
```

5. 登录成功后响应为 302，并通过 `Set-Cookie` 下发：

```text
_member_user_tonken_
```

6. 业务域登录态校验：

```text
GET https://dc.oilchem.net/ndc/common/getUserId
Header: token: _member_user_tonken_=<token>
```

返回 `response` 为非 0 时视为登录有效。

## 代码约束

- 不保存 `_pass`。即便响应或 session 中有该 cookie，也会被过滤。
- 不在代码中写死账号、密码、token、cookie 或 validate。
- 不伪造网易易盾校验，只接收外部已经获得的 validate。
