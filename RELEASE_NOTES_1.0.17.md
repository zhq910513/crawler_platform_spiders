# crawler_platform_spiders v1.0.17

## 变更

- 撤回 v1.0.16 主动外部 CI/CD 发布方案。
- 删除主动 GitHub Actions Release 注册 workflow。
- 删除 `crawler_project.example.json`，避免业务仓库保存平台归属/发布配置。
- 移除主动注册 CLI 入口和 `scripts/platform_register.py`。
- 新增 `scripts/platform_build_contract.sh`，作为 crawler_platform 构建中心的被动调用契约。
- `scripts/build_and_register.sh` 改为 fail-closed，防止误推镜像或误注册平台。
- `.env.example` 只保留本地调试和 manifest 构建变量，不再包含平台 token 或 registry secret 字段。
- 新增 `docs/PASSIVE_PLATFORM_BUILD_CONTRACT_1.0.17.md`。

## 边界

本仓库只提供：任务发现、契约校验、Manifest 生成、运行时入口和业务爬虫代码。Release 注册、镜像推送、Manifest Diff、Release 激活与生产调度事实由 crawler_platform 管理。
