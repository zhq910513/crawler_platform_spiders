# crawler_platform_spiders v1.0.18

## 修复

- 修复 `python:3.12-slim` 镜像中可编辑安装失败：在执行 editable install 前显式安装 `pyproject.toml` 已声明的 `setuptools>=68` 与 `wheel`。
- 保留项目自 v1.0.2 起既有的 `--no-build-isolation --no-deps -e .` 构建策略，避免 editable 阶段再次创建隔离环境并重复下载 PEP 517 build dependencies。
- 默认镜像与浏览器镜像统一使用 `python -m pip`，并通过 `${PIP_INDEX_URL}` 安装 pip、build backend 与运行依赖。
- `Dockerfile`、`Dockerfile.browser`、`VERSION`、`pyproject.toml`、本地示例和运行时版本回退统一为 `1.0.18`。

## 契约清理

- 按 v1.0.17 已确立的“平台被动构建发现标准包”契约，移除残留的主动 GitHub Actions 发布 workflow、`crawler_project.example.json` 和 `scripts/platform_register.py`。
- 删除与 v1.0.17 被动构建契约冲突的 v1.0.16 主动外部 CI 发布回归测试。
- 新增 v1.0.18 镜像 packaging 回归测试，要求两个 Dockerfile 在 `--no-build-isolation` 前显式准备声明的 build backend，防止 Python slim 基础镜像再次因缺少构建依赖而失败。

## 根因

`pyproject.toml` 使用 `setuptools.build_meta`，并声明构建依赖 `setuptools>=68` 与 `wheel`。原 Dockerfile 直接执行 `pip install --no-build-isolation --no-deps -e .`；该参数要求调用方自行准备构建依赖，但 `python:3.12-slim` 不保证预装 setuptools/wheel。复现结果为 `BackendUnavailable: Cannot import 'setuptools.build_meta'`，pip 以 exit code 2 退出。v1.0.18 在前置镜像层显式安装这两个声明依赖，从而保持原有无隔离 editable 构建策略并修复该失败。
