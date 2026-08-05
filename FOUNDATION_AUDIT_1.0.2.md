# crawler_platform_spiders 1.0.2 深度优化审计说明

## 审计结论

1.0.1 已经具备任务发现、runtime、日志、退出码、Docker 和基础插件，但交付目录中存在 `crawler_platform_spiders/crawler_platform_spiders` 双重同名目录，容易让维护人员误判为重复文件夹。1.0.2 已将通用核心库改名为 `crawler_foundation`，项目名和镜像名仍保持 `crawler_platform_spiders`。

## 为什么不再用内层 `crawler_platform_spiders` 包名

Python 项目常见“项目目录名 = 包名”的结构，但对交付型压缩包不够友好。客户或实施人员解压时通常会看到：

```text
crawler_platform_spiders-foundation-1.0.1/crawler_platform_spiders/crawler_platform_spiders
```

虽然技术上正确，但容易误解。1.0.2 改为：

```text
crawler_platform_spiders/
  crawler_foundation/
  crawler_platform_spiders.py
  crawler_runtime/
  spiders/
  open_api/
  plugins/
```

其中：

- `crawler_foundation/`：公共基建包。
- `crawler_platform_spiders.py`：兼容 `python -m crawler_platform_spiders` 的入口文件。
- `spiders/` 和 `open_api/`：后续新增平台业务代码的主要位置。

## 对后续新增平台的影响

新增平台爬虫时，业务代码推荐导入：

```python
from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task
```

后续不需要再理解同名嵌套包，只需要关注：

```text
spiders/<platform>/
open_api/<platform>/
```

## 本轮额外加固

- 支持异步任务装饰器。
- 新增任务模板生成脚本。
- 完整校验 `sch.py` 与业务模块静态定义一致。
- `sync_sch.py` 原子写入。
- 版本默认值去硬编码。
