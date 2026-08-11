# crawler_platform_spiders 1.0.5 发布说明

## 版本定位

本版本把爬虫项目基建从“可被平台解析和执行”升级为“适配多 Agent、多服务器、CI/CD 统一构建发布”的交付模式。

## 核心变化

- 新增 `scripts/platform_register.py`：生成 manifest 并上报 crawler_platform 的 `POST /api/v1/discovered-projects`。
- 新增 `scripts/build_and_register.sh`：完成校验、Docker 构建、可选推送、digest 获取和平台注册。
- 新增 `.env.platform.example`：提供平台地址、Discovery token、公司、服务器编码、镜像仓库等发布参数样例。
- 新增 `docs/PLATFORM_INTEGRATION.md`：明确多设备部署原则：CI/CD 构建一次镜像，平台注册一次版本，多台 Agent 按 digest 拉取执行。
- 新增 GitHub Actions 样例 `.github/workflows/crawler-platform-spiders.yml`。
- 新增平台发布注册测试，覆盖 dry-run、多 serverCode、真实 HTTP POST 请求结构和 shell 语法检查。

## 多设备部署结论

不建议每台服务器独立 `git pull && docker build`。生产模式应使用统一镜像仓库和镜像 digest：

```text
Git → CI/CD → Docker registry → crawler_platform 项目版本 → 多台 Agent 拉同一个 digest 执行
```

## 验证

```text
python scripts/sync_sch.py --check
python scripts/validate_tasks.py
python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins scripts
pytest -q
bash -n scripts/build_and_register.sh
```
