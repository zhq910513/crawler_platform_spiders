# crawler_platform_spiders 1.0.2 发布说明

## 版本定位

本版本是通用爬虫项目基建的第一轮深度审计整改版，目标是让后续新增平台爬虫时尽量只改 `/spiders` 与 `/open_api`，不再重复修改公共运行骨架。

## 主要变更

1. 新增静态任务发现机制。
   - 业务模块可声明 `TASK_DEFINITION = {...}` 或 `TASKS = [{...}]`。
   - 新增 `crawler_foundation.tasks.discovery.discover_tasks()`。
   - 新增 `scripts/sync_sch.py --write/--check`。
   - 根目录 `sch.py` 改为由业务模块静态定义生成。

2. 修复任务失败被平台误判成功的风险。
   - `@platform_task` 捕获 `CrawlerError` 时写入标准 `exitCode`。
   - `crawler_runtime` 根据 `runtime_result.status/error.exitCode` 返回非 0 进程退出码。
   - Agent 以容器退出码判定任务结果时可以正确识别失败。

3. 增强 Agent 与本地参数兼容。
   - `crawler_runtime` 支持合并 `CRAWLER_TASK_PARAMS_JSON` 与 `--kwargs-json`。
   - `TaskContext` 支持 `CRAWLER_*` 与简写环境变量。
   - 平台元字段进入 `TaskContext.payload`，但不会直接传入业务函数，避免 `unexpected keyword argument`。

4. 文档更新。
   - README 更新新增平台流程。
   - `docs/ADD_PLATFORM_TASK.md` 更新为只在业务目录声明任务定义并生成 sch.py 的流程。
   - 新增 `FOUNDATION_AUDIT_1.0.2.md`，记录深度审计结论和平台侧剩余配合点。

## 验证结果

```text
python scripts/sync_sch.py --check：通过
python scripts/validate_tasks.py：通过
python -m compileall：通过
pytest：7 passed
crawler_platform 1.0.22 parse_sch_manifest.py 解析 sch.py：通过
成功任务 runtime 退出码：0
失败任务 runtime 退出码：30
```

## 需要平台侧后续补强

crawler_platform Agent 1.0.22 当前未向任务容器注入 `CRAWLER_COMPANY_ID`。本基建已兼容读取该变量和 payload 中的 `companyId`，但要让业务代码稳定通过 `context.company_id` 获取公司 ID，平台 Agent 后续应补充注入。
