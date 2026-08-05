# crawler_platform_spiders 1.0.2 深度基建审计与整改说明

## 审计目标

验证项目是否真正满足：后续新增平台爬虫时，公共运行、日志、配置、任务发现、Docker、平台 Agent 入口不再重复改造；开发人员只需要在 `/spiders` 增加业务任务，必要时在 `/open_api` 增加接口封装。

## 本轮发现并修复的问题

### 1. 任务失败可能被 Agent 误判成功

1.0.0 中 `@platform_task` 捕获业务异常后返回 `{"status":"failed"}`，但 `crawler_runtime` 仍然返回进程退出码 0。平台 Agent 当前以容器退出码判断成功失败，因此登录失败、验证码失败、解析失败等可能被平台记录为成功。

1.0.2 已修复：

- `CrawlerError` 对应退出码会写入 `runtime_result.error.exitCode`。
- `crawler_runtime` 会根据 `runtime_result.status` 和 `exitCode` 返回非 0 退出码。
- 已补测试：模拟登录失败时退出码为 30。

### 2. 新增任务仍需手工维护 sch.py

1.0.0 中新增平台任务时除了写 `/spiders`，还必须手工编辑根目录 `sch.py`，容易漏字段、拼错入口或忘记同步。

1.0.2 已修复：

- 支持在业务模块内声明静态 `TASK_DEFINITION = {...}` 或 `TASKS = [{...}]`。
- 新增 `scripts/sync_sch.py --write`，从 `/spiders` 静态生成根目录 `sch.py`。
- 新增 `scripts/sync_sch.py --check`，用于 CI 检查 `sch.py` 是否和业务代码一致。
- `scripts/validate_tasks.py` 会同时校验 sch.py 与 spiders 任务定义一致。

### 3. Agent 参数环境与本地调试参数兼容不足

1.0.2 已增强：

- `crawler_runtime` 会把 `CRAWLER_TASK_PARAMS_JSON` 与 `--kwargs-json` 合并，命令行参数优先。
- `TaskContext` 会同时识别 `CRAWLER_*` 和简写环境变量，例如 `RUN_ID`、`TASK_CODE`、`PROJECT_ID`。
- 平台元字段会进入 `TaskContext.payload`，但不会直接传给业务函数，避免业务函数因为 `companyId`、`taskId` 等元字段报 `unexpected keyword argument`。

## 新增平台的推荐方式

在 `/spiders/<platform>/<task>.py` 中同时写任务定义和运行函数：

```python
from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task

TASK_DEFINITION = {
    "definitionKey": "demo_task",
    "taskName": "示例平台任务",
    "taskGroup": "demo",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "requiredCapabilities": {"browser": False},
    "resourceRequirements": {},
}

@platform_task()
def run(context, **kwargs):
    context.logger.info("业务开始", event="business_started")
    return TaskResult.success("完成")
```

然后执行：

```bash
python scripts/sync_sch.py --write && python scripts/validate_tasks.py
```

生成后的 `sch.py` 仍然是平台可以静态解析的纯字面量文件。

## 仍需平台侧配合的点

当前 crawler_platform Agent 1.0.22 已向任务容器注入 `CRAWLER_PROJECT_ID`、`CRAWLER_TASK_ID`、`CRAWLER_TASK_CODE` 等，但从源码看未注入 `CRAWLER_COMPANY_ID`。本基建已支持读取 `CRAWLER_COMPANY_ID` 和 payload 中的 `companyId`，但要让业务任务稳定拿到公司 ID，平台 Agent 后续应补充注入该环境变量。

这不是爬虫项目内部能完全兜底的问题，因为任务容器无法安全读取 Docker label 或平台 claim 原文。

## 本轮验证

- Python 编译通过。
- `scripts/sync_sch.py --check` 通过。
- `scripts/validate_tasks.py` 通过。
- `crawler_runtime` 成功任务退出码为 0。
- `crawler_runtime` 失败任务退出码按错误类型返回。
- pytest 契约测试通过。
