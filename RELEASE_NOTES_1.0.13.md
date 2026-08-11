# crawler_platform_spiders 1.0.13 发布说明

本版本继续固化爬虫项目开发结构，目标是让后续新增平台、任务、API/网页账号、对象亲和绑定等场景都能按统一模板开发。

## 主要变化

1. 新增 `spiders.common.standard` 统一导出入口，业务开发优先从这里导入标准基类和公共对象。
2. 新增 `AuthCacheRecord`，固化 Web Cookie、API Token、浏览器态的登录态缓存结构。
3. 新增 `BatchWriter / iter_batches / normalize_rows`，减少业务任务里重复写批量入库缓冲逻辑。
4. 新增 `StandardBusinessTask / StandardPageTask / StandardSubjectTask`，分别覆盖普通批量入库、分页任务、对象亲和查询任务。
5. 增强 `context.accounts` 对固定账号、多账号、账号池、平台租约返回账号、亲和绑定的解析能力。
6. 新增任务契约校验模块 `crawler_foundation.tasks.contract`，校验账号槽位、配置槽位、输出表、亲和绑定字段。
7. 重写 `scripts/create_task.py`，支持 `basic / page / subject / api` 四类标准模板。
8. 新增开发文档 `docs/SPIDER_DEVELOPMENT_STANDARD_1.0.13.md`。

## 开发约定

新业务优先使用：

```python
from spiders.common.standard import StandardPageTask, StandardSubjectTask, StandardApiBase
```

新增任务后执行：

```bash
python scripts/sync_sch.py --write && python scripts/validate_tasks.py
```

## 兼容性

不改变现有任务入口、`sch.py` 结构、账号状态事件协议和平台发布协议。
