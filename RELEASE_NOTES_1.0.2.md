# crawler_platform_spiders 1.0.2 发布说明

## 版本定位

本版本是爬虫项目通用基建的目录结构与开发体验优化版，重点解决压缩包解压后出现 `crawler_platform_spiders/crawler_platform_spiders` 双重同名目录带来的误解，同时继续降低新增平台爬虫时对公共层的改动概率。

## 主要变更

1. 优化目录命名。
   - 项目根目录仍建议命名为 `crawler_platform_spiders`。
   - 通用 Python 核心包从 `crawler_platform_spiders/` 调整为 `crawler_foundation/`。
   - 不再出现 `crawler_platform_spiders/crawler_platform_spiders` 双重同名目录。
   - 保留 `crawler_platform_spiders.py` 兼容入口，仍可执行 `python -m crawler_platform_spiders manifest`。

2. 新增任务模板生成脚本。
   - 新增 `scripts/create_task.py`。
   - 后续新增平台任务可直接生成 `/spiders/<platform>/<task>.py` 模板。
   - 生成后只需要补业务逻辑，再执行 `python scripts/sync_sch.py --write && python scripts/validate_tasks.py`。

3. 增强异步任务支持。
   - `@platform_task()` 现在支持装饰 `async def run(...)`。
   - 新增 `demo_async_echo` 示例任务和回归测试。

4. 加强任务清单校验。
   - `scripts/validate_tasks.py` 不再只比对入口字段，而是比对 `sch.py` 与 `/spiders` 下完整静态任务定义。
   - `scripts/sync_sch.py --write` 改为原子写入，避免生成过程中中断留下半文件。
   - 任务发现遇到语法错误或非静态任务定义时，错误信息更明确。

5. Docker editable 安装加固。
   - Dockerfile 与 Dockerfile.browser 使用 `pip install --no-build-isolation --no-deps -e .`，避免构建阶段重复拉取 PEP517 build 依赖。

6. 版本一致性整理。
   - `VERSION`、`.env.example`、Dockerfile、docker-compose 示例、pyproject、manifest 默认版本统一为 `1.0.2`。
   - `scripts/build_manifest.py` 默认使用当前包版本，不再硬编码旧版本。

## 新增平台任务推荐命令

普通接口任务：

```bash
python scripts/create_task.py --platform amazon --definition-key amazon_keyword_rank --task-name "Amazon 关键词排名采集" --write
```

浏览器任务：

```bash
python scripts/create_task.py --platform baidu --definition-key baidu_shop_detail --task-name "百度爱采购店铺详情" --browser --write
```

同步校验：

```bash
python scripts/sync_sch.py --write && python scripts/validate_tasks.py
```

## 验证结果

```text
python scripts/sync_sch.py --check：通过
python scripts/validate_tasks.py：通过
python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins scripts：通过
pytest -q：11 passed
python -m crawler_platform_spiders --version：1.0.2
python -m crawler_platform_spiders manifest：通过，输出 3 个任务定义
python -m crawler_runtime --entrypoint spiders.demo.async_echo:run --kwargs-json '{"text":"ok"}'：退出码 0
python -m crawler_runtime --entrypoint spiders.system.health:run --kwargs-json '{"raise_login_error":true}'：退出码 30
```

## 未完成验证

当前环境没有 Docker，因此未执行真实 Docker build。部署机或 CI 中建议执行：

```bash
docker build -t crawler_platform_spiders:1.0.2 .
```
