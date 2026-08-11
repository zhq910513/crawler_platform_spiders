# crawler_platform_spiders 1.0.12 发布说明

## 版本主题

补齐平台 1.0.19 上线门禁所需的爬虫端运行时契约：`context.config`、平台账号租约协议、账号 SDK 默认 payload、脱敏增强和运行时标准化调用。

## 关键变更

- 新增 `RuntimeConfigResolver`，支持从 `CRAWLER_CONFIG_JSON` / task payload 读取运行时配置和配置引用。
- `TaskContext` 正式提供 `context.config`，业务代码可统一调用 `context.config.mysql/redis/mongo/oss`。
- `AccountStatusReporter` 保存运行时 payload，`get/list/lease/resolve/affinity/external_affinity` 默认读取平台注入的账号槽位。
- `lease()` 支持通过平台租约 API 申请/释放账号，未配置租约端点时保持本地兼容语义。
- 增加运行时配置脱敏测试和平台租约协议测试。

## 上线注意

- 爬虫业务代码仍然只通过 `context.config` 和 `context.accounts` 获取运行时配置与账号。
- 业务代码禁止读取本地明文 `.env` 作为公司数据库或账号凭证来源。
