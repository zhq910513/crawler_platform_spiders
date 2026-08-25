# 京多多现货商品采集部署测试说明 v1.0.15

## 目标

用京多多小案例验证 crawler_platform_spiders 的标准任务结构：

```text
open_api/jdd/items_client.py  # HTTP 请求封装
spiders/jdd/base.py           # 京多多平台共享能力与 MongoDB 写入
spiders/jdd/items.py          # TASK_DEFINITION + 商品采集业务
```

## 配置来源

MongoDB 信息必须来自 crawler_platform 的公司资源配置，并绑定到任务配置槽位：

```text
mongo_jdd
```

业务参数中不再允许携带数据库连接信息。任务运行时通过：

```python
context.config.mongo("mongo_jdd")
```

读取平台下发的已解析配置。

## 公司资源配置建议

平台公司资源配置中建议配置为 MongoDB 资源，配置内容至少满足一种形式：

```json
{
  "uri": "mongodb://user:password@host:27017/jdd",
  "database": "jdd",
  "collection": "items"
}
```

或：

```json
{
  "host": "host",
  "port": 27017,
  "username": "user",
  "password": "password",
  "database": "jdd",
  "collection": "items"
}
```

真实密码只能保存在平台公司资源配置中，不能写入 Git、任务参数、文档示例或日志。

## 任务参数

推荐 dry-run：

```json
{"dryRun": true, "pageSize": 10, "pageNum": 1}
```

推荐写库测试：

```json
{"dryRun": false, "pageSize": 500, "pageNum": 1}
```

## 上线检查

- `jdd_items_sync` 能被 `scripts/sync_sch.py` 自动发现。
- `requiredConfigs.mongo_jdd.required = true`。
- 平台生产任务已绑定 `mongo_jdd`。
- Agent claim run 返回的 `CRAWLER_CONFIG_JSON.configs.mongo_jdd` 是已解析配置，不是绑定引用。
- dry-run 先成功，再执行写库测试。
