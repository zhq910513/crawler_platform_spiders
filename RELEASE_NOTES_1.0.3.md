# crawler_platform_spiders 1.0.4

## 目标

按照平台爬虫代码规范重构 Oilchem 登录代码，形成 `spiders/oilchem/base.py + login.py` 的标准结构，后续新增 Oilchem 业务只需要在 `spiders/oilchem/<业务名>.py` 编写具体业务逻辑。

## 主要变更

- 新增 `spiders/oilchem/base.py`：
  - 账号参数模型 `OilchemAccount`。
  - session 创建，优先 `curl_cffi`，不可用时退回 requests。
  - token/cookie 解析、标准 headers、GET/POST JSON、登录校验。
  - Redis/Mongo token/cookie 缓存，兼容历史 key：`oilchem_jwt_{username}`、`oilchem_jwt`、`oilchem_cookie`。
  - 删除硬编码账号和示例 token，全部改为任务参数或环境变量传入。
- 新增 `spiders/oilchem/login.py`：独立 Oilchem 登录校验任务 `oilchem_login_check`。
- 新增 `spiders/oilchem/example_business.py`：Oilchem 业务任务模板，不注册到平台。
- 新增 `docs/PLATFORM_SPIDER_STANDARD.md`：平台爬虫代码规范。
- 增强 `MySQLClient.insert_rows()`，业务模块可安全传入目标表进行批量入库。
- 修复 `crawler_foundation.tasks.discovery` 中任务定义非字面量时报错变量未初始化的问题。
- 版本升级为 1.0.4。

## 验证

- `python scripts/sync_sch.py --check`
- `python scripts/validate_tasks.py`
- `python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins scripts`
- `pytest -q`
- `python -m crawler_platform_spiders manifest`
- `python -m crawler_runtime --entrypoint spiders.oilchem.login:run --kwargs-json '{"username":"u"}'` 返回登录失败退出码 30，证明无 token 时不会误判成功。
