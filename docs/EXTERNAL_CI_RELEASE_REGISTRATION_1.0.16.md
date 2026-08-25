# 外部 CI 构建并注册 Release v1.0.16（已废弃）

该方案在 v1.0.17 被废弃。

原因：`crawler_platform_spiders` 不应该主动 CI/CD，不应该保存平台 Token，不应该主动调用 `crawler_platform` 注册 Release。

当前标准路径见：

```text
docs/PASSIVE_PLATFORM_BUILD_CONTRACT_1.0.17.md
```

职责边界：

```text
crawler_platform
  拉取代码、构建镜像、推送镜像、登记 Release、Manifest Diff、Release 激活、调度 Run。

crawler_platform_spiders
  提供稳定 Runtime Shell、TASK_DEFINITION、Discovery、Contract Validation、Manifest 生成。
```
