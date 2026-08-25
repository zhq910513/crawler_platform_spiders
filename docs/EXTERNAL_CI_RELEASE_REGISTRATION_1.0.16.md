# 外部 CI 构建并注册 Release v1.0.16

## 背景

crawler_platform v1.0.87 明确：平台构建中心未就绪时，平台不能直接读取 Git 仓库、构建镜像并推送镜像仓库。爬虫项目必须先由外部 CI 构建不可变镜像，并将 manifest 注册到平台。

## 标准链路

```text
crawler_platform_spiders
  ↓
GitHub Actions / GitLab CI
  ↓
静态校验 TASK_DEFINITION / sch.py
  ↓
构建并推送镜像
  ↓
取得 imageRepository + imageDigest
  ↓
生成 .release/crawler_manifest.json
  ↓
POST /api/v1/discovered-projects
  ↓
平台项目发布页匹配已登记 Release
```

## GitHub Actions

本仓库 v1.0.16 提供：

```text
.github/workflows/crawler-platform-spider-release.yml
```

该 workflow 会执行：

```text
sync_sch.py --check
validate_tasks.py
compileall
Docker build + push
scripts/platform_register.py
```

## 必需配置

至少配置：

```text
CRAWLER_CONTROL_BASE_URL
CRAWLER_DISCOVERY_TOKEN
CRAWLER_COMPANY_CODE
```

`CRAWLER_COMPANY_CODE` 推荐写入 `crawler_project.json`，也可以放在仓库变量里。

## 私有 HTTP Registry

如果镜像仓库是类似：

```text
42.193.226.138:5000
```

且没有 HTTPS，需要在 GitHub 仓库变量配置：

```text
CRAWLER_REGISTRY_HOST=42.193.226.138:5000
CRAWLER_REGISTRY_INSECURE=true
CRAWLER_REGISTRY_NAMESPACE=<namespace>
CRAWLER_IMAGE_REPOSITORY=42.193.226.138:5000/<namespace>/<project_code>
```

并在仓库 Secrets 配置：

```text
CRAWLER_REGISTRY_USERNAME
CRAWLER_REGISTRY_PASSWORD
```

如果 registry 没有认证，当前 workflow 不默认匿名推送，避免误把生产镜像推送权限做成隐式假设。

## 本地 dry-run

不访问平台，只生成 manifest 和请求 payload：

```bash
python scripts/platform_register.py \
  --platform-url http://127.0.0.1:8080 \
  --discovery-token dummy \
  --company-code demo_company \
  --image-repository registry.local/crawler_platform_spiders \
  --image-digest sha256:1111111111111111111111111111111111111111111111111111111111111111 \
  --release-version 1.0.16 \
  --dry-run
```

生成文件：

```text
.release/crawler_manifest.json
.release/discovered-project.json
```

## 注意

- 不能用 `latest/main/dev` 注册 Release。
- `imageDigest` 必须是 registry 返回的 `sha256:<64 hex>`。
- CI 只注册 Release，不直接创建生产任务、不绑定 MongoDB、不修改平台调度事实。
- JDD 任务仍然要求平台生产任务绑定 `mongo_jdd` 公司资源配置。
