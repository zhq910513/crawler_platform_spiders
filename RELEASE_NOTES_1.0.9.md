# crawler_platform_spiders 1.0.9 发布说明

## 版本定位

本版本配合 crawler_platform 1.0.16，补齐多公司、多服务器、多项目交付下的爬虫项目侧规范：任务定义显式支持离线兜底策略，运行上下文提供轻量 checkpoint SDK，业务爬虫后续只需要在 `/spiders/平台名/base.py + 业务名.py` 或 `/open_api/平台名` 中迭代。

## 新增能力

- `TASK_DEFINITION` 支持：
  - `allowOfflineRun`
  - `offlinePolicy`
- `scripts/sync_sch.py` 会把离线兜底字段同步到根目录 `sch.py`。
- `TaskContext` 新增：
  - `context.checkpoint.load(key, default)`
  - `context.checkpoint.save(key, value)`
  - `context.checkpoint.mark_done()`
- 新增 `crawler_foundation.checkpoint.FileCheckpoint`，默认写入 `/cache/checkpoints/`，用于业务任务实现断点续爬。
- Oilchem 登录校验任务默认不允许离线执行，避免平台失联时重复请求过期 cookie。
- 示例任务默认补齐离线字段，确保 manifest 与平台 1.0.16 合同一致。

## 使用原则

- 测试环境仍可传 `cookieString`。
- 生产环境推荐传 `cookieSecretRef`，由平台密钥库或 Agent 运行时注入。
- 真正断点续爬必须由业务任务保存 checkpoint，平台只负责不中断运行中的容器和离线快照调度约束。
