# crawler_platform_spiders 1.0.11 发布说明

本版本在 1.0.10 账号状态上报公共组件基础上，落地“爬虫项目标准契约 v1”和账号组合公共方法。

## 新增能力

- `TASK_DEFINITION` 自动补齐并输出：`platformCode`、`requiredConfigs`、`requiredCredentials`、`outputTables`、`contractVersion`。
- 新增 `AuthState` 标准登录态对象。
- `AccountStatusReporter` 增强：
  - `get(slot)` 固定账号
  - `list(slot)` 固定多账号
  - `lease(slot)` 账号池租约兼容入口
  - `resolve(slot, subject)` 按规则解析账号
  - `affinity(slot, subjectType, subjectKey)` 对象账号亲和绑定
  - `external_affinity(...)` 外部缓存对象账号绑定兼容
  - `commit_subject_success(...)` 查询成功后提交绑定事件
  - `auth(account)` 获取标准登录态
  - `mask(account)` 脱敏输出
- 新增标准基类：`StandardPlatformBase`、`StandardWebBase`、`StandardApiBase`、`StandardSubjectQueryTask`。
- 新增标准异常：`RequestRetryableError`、`RequestFatalError`、`AccountAuthError`、`AccountVerifyRequiredError`、`AccountRateLimitedError`、`StorageError`。
- 新增文档 `docs/SPIDER_PROJECT_CONTRACT_V1.md`。

## 校验

- 爬虫项目测试：`26 passed`
- `python -m compileall`：通过
