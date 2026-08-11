# 离线运行与断点续爬标准（1.0.13）

## 任务定义字段

每个任务定义必须显式声明：

- allowOfflineRun：是否允许 Agent 在平台失联时按离线快照运行。
- offlinePolicy：离线运行限制策略。
- idempotencyPolicy：任务幂等语义。

示例：

```python
TASK_DEFINITION = {
    "definitionKey": "demo_echo",
    "taskName": "Demo Echo",
    "entryModule": "spiders.demo.echo",
    "entryFunction": "run",
    "allowOfflineRun": True,
    "offlinePolicy": {
        "maxOfflineHours": 24,
        "maxOfflineRuns": 48,
        "catchUp": False,
    },
}
```

## 何时允许离线运行

适合离线运行：

- 定时采集
- 幂等写入
- 已实现 checkpoint
- 允许失败重试

不适合离线运行：

- 登录态刷新类任务
- 非幂等写入
- 需要平台动态分片
- 依赖人工确认参数
- 密钥未缓存或不允许离线使用

## checkpoint 使用

运行上下文提供 `context.checkpoint`，业务代码应在处理每一页、每一批或每个关键游标后保存进度。

```python
last_page = context.checkpoint.load("last_page", 1)
for page in range(last_page, max_page + 1):
    crawl_page(page)
    context.checkpoint.save("last_page", page + 1)
context.checkpoint.mark_done()
```

断点续爬是业务代码职责，平台只能保证不在同一个 run 中途切换镜像，不能自动推断业务游标。
