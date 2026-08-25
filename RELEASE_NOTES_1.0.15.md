# Release Notes 1.0.16

## 变更类型

爬虫项目标准化修复。

## 背景

v1.0.14 将京多多小案例改成可运行任务，但仍允许通过任务参数传入 MongoDB 连接信息，这不符合 crawler_platform 的公司资源配置驱动标准。v1.0.16 废弃该实验路径，改为固定平台目录结构和平台运行时配置读取方式。

## 本轮变更

- 新增 `spiders/jdd/base.py`，承载京多多平台共享能力。
- `spiders/jdd/items.py` 只保留业务采集、解析、结果写入编排。
- `open_api/jdd/items_client.py` 继续只负责京多多接口请求封装，不写库、不读平台配置。
- `TASK_DEFINITION.requiredConfigs` 中 `mongo_jdd` 改为必需配置。
- `TASK_DEFINITION.outputTables` 声明 `jdd.items`，写入方式为 `upsert`。
- 删除通过任务参数传数据库配置的实验入口。
- 更新自动发现产物 `sch.py`。
- 新增/更新 JDD 结构标准、运行配置、自动发现、敏感信息检查测试。

## 运行约束

业务代码必须通过：

```python
context.config.mongo("mongo_jdd")
```

读取平台/公司资源配置。平台必须在运行时下发已解析 MongoDB 配置；如果只下发绑定引用，任务会明确报配置错误，不会猜测数据库连接。

## 测试

- `python -m compileall -q crawler_foundation crawler_runtime plugins open_api spiders tests scripts`
- `python scripts/sync_sch.py --check`
- `python scripts/validate_tasks.py`
- `pytest`
- 敏感信息与废弃任务参数 grep
- ZIP 解压 manifest 校验
