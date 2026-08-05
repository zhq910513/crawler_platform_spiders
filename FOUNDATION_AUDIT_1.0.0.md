# crawler_platform_spiders 1.0.0 基建整改说明

## 当前输入包审计结论

原始包已经具备任务模型、结构化日志、资源封装和本地 runner 雏形，但存在几个不适合作为长期项目基建的问题：

1. 压缩包根目录直接放置 `__init__.py`、`runner.py` 等包文件，实际导入路径与 `crawler_platform_spiders` 包名不完全一致，容易在 Docker 或平台 Agent 环境中导入失败。
2. 原 runner 主要是 task/resources/secrets/result 文件模式，与当前 crawler_platform Agent 实际调用方式 `python -m crawler_runtime --entrypoint ... --kwargs-json ...` 不完全对齐。
3. 缺少平台静态解析需要的根目录 `sch.py`。
4. 缺少标准 `/spiders`、`/open_api`、`/plugins` 分层，后续新增平台爬虫容易继续混杂公共代码和业务代码。
5. 缺少 Dockerfile、.env.example、README、任务校验脚本和基础契约测试。

## 本次整改目标

本次将项目重构为稳定通用基建，具体平台业务代码后续只需要增加到：

- `/spiders/<platform>/...`
- `/open_api/<platform>/...`

然后在 `sch.py` 追加静态任务定义即可。

## 已完成能力

- 标准 Python 包结构。
- 内置 `crawler_runtime`，兼容 crawler_platform Agent 启动命令。
- 根目录 `sch.py` 静态任务清单，兼容平台 `parse_sch_manifest.py`。
- 本地 CLI：manifest、run。
- 统一运行上下文：runId、projectId、taskCode、shard、目录、资源锁等。
- 结构化 JSON 日志和敏感字段脱敏。
- 统一 TaskResult。
- 统一异常和退出码语义。
- 通用 retry 工具。
- 通用 HTTP session。
- MySQL/Redis/Mongo 基础封装。
- 邮件/Webhook 通知基础封装。
- OSS 文件上传和媒体待上传行构建工具。
- 验证码插件预留。
- API Spider、Browser Spider 基类。
- system_health 和 demo_echo 两个示例任务。
- Dockerfile、Dockerfile.browser、docker-compose.example.yml。
- README 和新增平台任务文档。
- 基础契约测试。

## 验证结果

```text
python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins scripts：通过
python scripts/validate_tasks.py：通过
pytest -q：4 passed
python -m crawler_platform_spiders manifest：通过
crawler_platform 1.0.12 cicd/parse_sch_manifest.py 解析 sch.py：通过
```

## 未在当前环境完成的验证

当前环境没有 Docker，因此未执行真实 Docker build。请在部署机或 CI 中执行：

```bash
docker build -t crawler_platform_spiders:1.0.0 .
```
