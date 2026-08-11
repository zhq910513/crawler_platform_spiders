# crawler_platform_spiders 与 crawler_platform 联通规范

## 目标

一份爬虫项目代码可能被多台服务器执行，因此发布流程不能设计成“每台服务器 git pull 后各自 build”。标准模式是：代码只构建一次，镜像只发布一次，任务定义只注册一次，多台服务器上的 Agent 由 crawler_platform 统一调度并拉取同一个镜像版本执行。

## 推荐链路

```text
开发者提交代码
  ↓
CI 执行测试、任务定义校验、Docker 构建
  ↓
CI 推送镜像到统一 registry
  ↓
CI 把 manifest、imageRepository、imageDigest、releaseVersion 上报到 crawler_platform
  ↓
crawler_platform 前端出现新项目版本和任务定义
  ↓
操作员在平台选择服务器/服务器组、配置任务参数、启停调度
  ↓
各服务器 Agent 按平台指令 docker pull 并运行任务容器
```

## 操作员职责边界

正式交付时，操作员不应逐个运行 Python 文件，也不应在每台设备上手工 git pull。操作员只需要安装一次 crawler-agent，然后在平台页面选择版本、配置参数、选择服务器或服务器组。

过渡期如果还没有镜像仓库，可以先在一台服务器构建镜像并注册平台；多台设备生产执行仍建议尽快切换到 registry + digest 模式。

## 项目发布命令

CI 或发布机执行：

```bash
bash scripts/build_and_register.sh
```

脚本会执行：

```text
sync_sch 检查
任务定义校验
Python 编译
Docker build
可选 Docker push
生成 crawler_manifest.json
生成 discovered-project.json
POST /api/v1/discovered-projects
```

## 仅注册不构建

如果镜像已经由 CI 构建并取得 digest，可以只执行：

```bash
python scripts/platform_register.py --platform-url http://127.0.0.1:8000 --discovery-token xxx --company-id 1 --image-repository registry.example.com/crawler_platform_spiders --image-digest sha256:0000000000000000000000000000000000000000000000000000000000000000 --release-version 1.0.12
```

crawler_platform 1.0.13 起不再强制传 `--server-code`。不传时只注册 release；传入 `--server-code` 或 `CRAWLER_PLATFORM_SERVER_CODES` 时，会作为初始服务器池提示一起上报。最终是否调度到某台设备仍由 crawler_platform 的项目服务器池、任务指定服务器、Agent 标签和资源状态决定。

## 多台设备发布原则

不要让每台设备独立构建镜像。多台设备要执行同一个项目版本时，应使用：

```text
imageRepository: registry.example.com/crawler_platform_spiders
imageDigest: sha256:...
releaseVersion: 1.0.12
```

Agent 应按 digest 拉取，避免 tag 被覆盖后执行记录无法追溯。

## 敏感参数

以下内容不允许写入 Git、sch.py、Docker 镜像或 README 真实示例：

```text
Oilchem cookieString
账号密码
Redis 密码
Mongo 密码
MySQL 密码
代理账号
平台 Discovery token
```

这些应放在 CI Secret、平台任务参数、公司级密钥、项目级密钥或服务器本地 `.env.platform`。
