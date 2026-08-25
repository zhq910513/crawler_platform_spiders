# Release Notes 1.0.16

## 目标

补齐爬虫项目外部 CI 发布路径，使 crawler_platform v1.0.87 的“未登记 Release 必须卡住”有真实可用的构建注册产物。

## 变更

- 新增标准 GitHub Actions workflow：`.github/workflows/crawler-platform-spider-release.yml`。
- 废弃旧的 `.github/workflows/crawler-platform-spiders.yml`，避免继续使用旧的 companyId/serverCode 注册路径作为默认主线。
- `scripts/platform_register.py` / `crawler_foundation.platform.register` 支持 `companyCode` 注册方式。
- `build_manifest()` 支持写入 `companyCode` 与 `supportedArch`。
- `.env.example` 增加外部 CI 注册相关变量。
- 新增 `crawler_project.example.json`，用于说明项目归属配置。
- 新增外部 CI 发布文档与防回归测试。

## 不做

- 不实现平台构建中心。
- 不读取 Git 私有仓库凭据。
- 不假设镜像仓库推送凭据结构。
- 不在爬虫任务参数中传数据库连接。

## 兼容性

- 仍兼容旧的 `companyId` dry-run / 注册参数。
- 新平台推荐使用 `companyCode + CRAWLER_DISCOVERY_TOKEN`。
