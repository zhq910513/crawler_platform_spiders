# crawler_platform_spiders

`crawler_platform_spiders` 是 `crawler_platform` 的爬虫执行项目。

它只负责一次任务运行：读取任务与资源清单、定位已注册爬虫入口、执行 `run(context)`、输出结构化日志、写入结果文件并退出。

## 关键边界

- 平台服务器与爬虫服务器可以完全分离。
- `crawler_agent` 在爬虫服务器启动临时容器并采集 stdout/stderr。
- 爬虫容器不直接连接 `crawler_platform`，也不持有平台认证信息。
- ERROR 日志由 Agent 实时同步到平台，网络中断时由 Agent 本地持久化并补传。
- 一个 TaskRun 对应一个独立容器。
- `/spiders` 内部自行完成登录、翻页、解析和入库。
- 公共运行层只约定 `run(context) -> TaskResult`。

## 本地运行

    python -m crawler_platform_spiders run --mode local --task-file examples/task.json --resources-file examples/resources.json --secrets-file examples/secrets.example.json --result-file .runtime/result.json --human-logs

## 服务器运行

    python -m crawler_platform_spiders run --mode server --task-file /run/crawler/task.json --resources-file /run/crawler/resources.json --secrets-file /run/crawler/secrets.json --result-file /run/crawler/result.json --errors-file /run/crawler/errors.ndjson --last-error-file /run/crawler/last_error.json

## 发布清单

    python -m crawler_platform_spiders manifest

平台导入发布清单后，可识别镜像中的任务入口、参数 Schema、镜像类型和所需逻辑资源。

详细协议见 `docs/`。
