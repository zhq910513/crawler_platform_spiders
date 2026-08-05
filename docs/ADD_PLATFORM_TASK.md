# 新增平台爬虫任务说明

新增平台时只改两类业务目录：

1. `/spiders/<platform>/`：业务任务入口，必须声明静态 `TASK_DEFINITION` 或 `TASKS`。
2. `/open_api/<platform>/`：接口封装，可选。

根目录 `sch.py` 不再手工维护，由同步脚本生成。


## 推荐生成任务模板

新增普通接口型任务：

```bash
python scripts/create_task.py --platform amazon --definition-key amazon_keyword_rank --task-name "Amazon 关键词排名采集" --write
```

新增浏览器任务：

```bash
python scripts/create_task.py --platform baidu --definition-key baidu_shop_detail --task-name "百度爱采购店铺详情" --browser --write
```

生成后只需要在新文件的 `run(context, **kwargs)` 中补业务逻辑，再执行同步校验。

## 单任务模块示例

```python
from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task

TASK_DEFINITION = {
    "definitionKey": "amazon_keyword_rank",
    "taskName": "Amazon 关键词排名采集",
    "taskGroup": "amazon",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "requiredCapabilities": {"browser": False},
    "resourceRequirements": {},
    "taskMaxConcurrency": 1,
    "groupMaxConcurrency": 4,
}

@platform_task()
def run(context, country: str = "US", keyword: str = ""):
    context.logger.info("任务开始", event="business_started", country=country, keyword=keyword)
    return TaskResult.success("完成")
```

## 多任务模块示例

```python
TASKS = [
    {"definitionKey": "task_a", "taskName": "任务A", "taskGroup": "demo"},
    {"definitionKey": "task_b", "taskName": "任务B", "taskGroup": "demo", "entryFunction": "run_b"},
]
```

每个任务的 `entryFunction` 必须在当前模块里真实存在。

## 同步到平台清单

```bash
python scripts/sync_sch.py --write && python scripts/validate_tasks.py
```

`sync_sch.py` 只做 AST 静态解析，不 import 业务模块，不会触发登录、网络请求或数据库连接。

## 平台 Agent 调用方式

任务入口必须能被平台 Agent 这样调用：

```bash
python -m crawler_runtime --entrypoint spiders.<platform>.<module>:run --kwargs-json '{}'
```

## 失败处理

业务代码中优先抛出公共异常：

```python
from crawler_foundation.core.exceptions import LoginError, NetworkError, ParseError
```

不要直接 `sys.exit()`。由 `@platform_task` 和 `crawler_runtime` 统一转换为平台可识别的退出码。
