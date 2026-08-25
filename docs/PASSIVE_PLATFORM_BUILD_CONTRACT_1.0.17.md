# 平台被动构建发现标准包 v1.0.17

## 目标

`crawler_platform_spiders` 是长期稳定的 Crawler Runtime Shell / SDK Distribution。它不主动 CI/CD，不主动注册平台，不保存平台 Token 或镜像仓库推送凭据。

新增平台爬虫时，常态变化只发生在：

```text
spiders/<platform>/**
open_api/<platform>/**
tests/business/** 或对应测试文件
fixtures/**
```

## 平台调用契约

`crawler_platform` 构建中心 / 构建执行器拉取源码后，在隔离构建目录中调用：

```bash
bash scripts/platform_build_contract.sh
```

该脚本执行：

```bash
python scripts/sync_sch.py --check
python scripts/validate_tasks.py
python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins scripts
python scripts/build_manifest.py --output .release/crawler_manifest.json
```

输出：

```text
.release/crawler_manifest.json
```

## 由平台注入的构建变量

平台构建器可以在调用脚本前注入：

```text
PROJECT_KEY
PROJECT_CODE
PROJECT_NAME
IMAGE_REPOSITORY
IMAGE_DIGEST
RELEASE_VERSION
RELEASE_CHANNEL
REPOSITORY_URL
GIT_BRANCH
GIT_COMMIT
CRAWLER_SUPPORTED_ARCH
```

这些是构建环境变量，不是仓库内持久配置。

## 禁止事项

爬虫项目不得：

```text
保存 crawler_platform API Token
保存 Discovery Token
保存镜像仓库推送用户名/密码
主动调用 crawler_platform 注册 Release
主动决定生产部署节点
保存生产调度事实
```

## 热更新关系

平台构建新 Release 后，只有新 Run 使用新 imageDigest。已经创建的 Run、排队 Run、运行中 Run 均继续使用自身 Run Snapshot 中冻结的 releaseId / imageDigest / entryModule / entryFunction / 参数与资源绑定快照。

## 已废弃入口

```text
scripts/build_and_register.sh
```

该脚本现在 fail-closed，用于阻止误走旧的主动发布路径。
