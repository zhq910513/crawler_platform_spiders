# 爬虫项目发布、Agent 更新感知与不中断运行说明（crawler_platform_spiders 1.0.13）

## 发布后执行服务器如何知道有新版本

本项目不要求每台执行服务器拉取源码。开发者推送代码后，CI/CD 构建一次镜像并推送到 registry，然后执行：

```bash
python scripts/platform_register.py
```

注册内容包含：

- `releaseVersion`
- `imageRepository`
- `imageDigest`
- `taskDefinitions`

crawler_platform 注册成功后，会把项目服务器池中的对应 Agent 节点标记为 `OUTDATED`。Agent 下一次心跳会收到 `pendingImagePulls`，由平台通知它有新镜像需要预热。

## B 服务器正在运行任务时如何处理

不会打断。

运行中的容器已经按 run 创建时保存的 `imageDigest` 启动。新 release 只影响后续新 run。Agent 检测到本机仍有运行实例时，不主动预热新镜像，而是等待空闲后再拉取。

## 断点续爬边界

平台只保证不中断、不换镜像、不让同一个 run 前后代码不一致。断点续爬必须由具体业务任务实现，例如：

- 按主键幂等入库。
- 把分页游标写入 MySQL/Redis。
- 下载任务记录文件状态。
- 失败重试时从 checkpoint 继续。

业务代码不要依赖“镜像更新后自动从中间继续”。

## 对平台版本要求

建议配套：

- crawler_platform >= 1.0.14
- crawler_platform_spiders >= 1.0.13

如果平台低于 1.0.14，release 注册仍可用，但 Agent 不会通过心跳收到 `pendingImagePulls`，只能在领取任务时按 digest 拉取镜像。
