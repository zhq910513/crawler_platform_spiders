# crawler_platform_spiders 1.0.6 发布说明

本版本配合 crawler_platform 1.0.13，完成“CI/CD 构建一次镜像、平台注册一次 release、多台 Agent 按 digest 执行”的发布闭环。

## 核心变化

- `scripts/platform_register.py` 默认支持 release-only 注册，不再强制传 `--server-code`。
- 仍兼容 `--server-code` / `CRAWLER_PLATFORM_SERVER_CODES`，用于向平台提供初始服务器池提示。
- 生成的 `discovered-project.json` 由多请求列表简化为单请求对象，包含 `companyId`、`manifest`，有服务器提示时再带 `serverCodes`。
- `.env.platform.example`、GitHub Actions 和文档均调整为平台 1.0.13 的多 Agent 发布模式。

## 推荐流程

开发者只提交代码；CI 构建并推送镜像，拿到 registry digest 后调用平台注册 release；操作员在 crawler_platform 里选择项目版本、配置服务器池和任务参数。
