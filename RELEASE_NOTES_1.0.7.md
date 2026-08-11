# crawler_platform_spiders 1.0.7 发布说明

## 版本定位

配套 crawler_platform 1.0.14，补齐多 Agent 场景下的发布认知和不中断运行说明。

## 调整内容

- 版本升级为 1.0.7。
- 文档明确：爬虫项目不在各执行服务器 `git pull`；CI/CD 构建一次镜像并注册平台 release。
- 文档明确：执行服务器通过平台 Agent 心跳 `pendingImagePulls` 感知新版本。
- 文档明确：B 服务器运行中任务不会被镜像更新打断，新 release 只影响后续 run。
- 文档明确：断点续爬由业务代码 checkpoint 实现，平台不做强制中断式迁移。

## 兼容性

- 继续兼容 Oilchem cookieString 登录校验任务。
- 继续兼容 release-only 注册模式。
- 推荐配套 crawler_platform >= 1.0.14。
