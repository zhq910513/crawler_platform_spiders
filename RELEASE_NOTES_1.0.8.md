# crawler_platform_spiders 1.0.9 发布说明

## 版本定位

本版本继续完善通用爬虫项目与 crawler_platform 多 Agent 发布模式的配套能力，重点收口 CI 发布不可变性、生成文件污染和敏感 cookie 参数规范。

## 核心优化

- GitHub Actions 拆分为 `validate` 与 `release-register` 两个 job。
- main 分支 push 只做校验，不再直接构建并注册平台 release。
- 只有 `v*` tag 才会构建镜像、推送 registry 并注册 crawler_platform。
- tag `v1.0.9` 会解析为平台注册版本 `1.0.9`，避免平台语义版本校验失败。
- `scripts/platform_register.py` 强制 releaseVersion 必须为 `x.y.z` 且必须与项目 VERSION 一致。
- 注册输出默认写入 `.release/`，并从 ZIP 中清除根目录 `crawler_manifest.json`、`discovered-project.json` 这类生成文件。
- Oilchem 登录任务继续兼容 `cookieString`，并新增 `cookieSecretRef` 参数约定，便于后续接平台密钥库或环境变量注入。

## 使用建议

- 测试时可以继续传 `cookieString`。
- 生产建议逐步迁移为 `cookieSecretRef`，由平台或 Agent 运行时注入对应密钥值，避免完整 cookie 长期保存在任务参数中。
