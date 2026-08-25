# crawler_platform_spiders

`crawler_platform_spiders` 是与 `crawler_platform` 配套的通用爬虫项目基建。公共层负责运行入口、任务发现、配置、日志、错误退出码、Docker 构建和平台 Agent 适配；具体平台爬虫后续只需要放入 `/spiders`，接口封装放入 `/open_api`。

当前基建版本：`1.0.16`

## 核心目标

- 不把具体平台业务代码写进公共层。
- 生产入口兼容 crawler_platform Agent：`python -m crawler_runtime --entrypoint spiders.xxx:run --kwargs-json '{}'`。
- 本地调试入口兼容开发人员：`python -m crawler_platform_spiders run --task-code system_health --kwargs-json '{}'`。
- 任务定义放在业务模块的静态 `TASK_DEFINITION` 或 `TASKS` 中。
- 根目录 `sch.py` 由 `scripts/sync_sch.py` 生成，仍然保持平台可静态解析的字面量文件。
- 后续新增平台时，只新增 `/spiders/<platform>/...` 或 `/open_api/<platform>/...`，再执行同步脚本，不再改公共运行骨架。

## 目录

```text
crawler_platform_spiders/
  sch.py                         # 平台静态任务清单，由 scripts/sync_sch.py 生成
  crawler_runtime/               # 平台 Agent 调用的轻量 runtime
  crawler_foundation/            # 通用核心库，避免外层项目目录和内层 Python 包同名
  plugins/                       # DB、HTTP、通知、OSS、验证码等通用插件
  open_api/                      # 开放接口类爬虫公共封装与平台实现
  spiders/                       # 具体平台爬虫与通用 Spider 基类
  scripts/                       # manifest、任务同步、体检等工具
  tests/                         # 基建契约测试
```


## 目录命名说明

解压后建议项目根目录仍叫 `crawler_platform_spiders`，但通用 Python 核心包已改名为 `crawler_foundation`，因此不会再出现 `crawler_platform_spiders/crawler_platform_spiders` 这种容易误解的双重同名目录。

仍然保留本地兼容入口：

```bash
python -m crawler_platform_spiders manifest
```

新增业务代码时请导入：

```python
from crawler_foundation.core.result import TaskResult
```

## 本地运行

```bash
python -m crawler_platform_spiders manifest
```

```bash
python -m crawler_platform_spiders run --task-code system_health --kwargs-json '{"message":"local ok"}'
```

```bash
python -m crawler_runtime --entrypoint spiders.system.health:run --kwargs-json '{"message":"runtime ok"}'
```

## 新增平台爬虫

第一步，在 `/spiders/<platform>/<task>.py` 新增业务任务：

```python
from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task

TASK_DEFINITION = {
    "definitionKey": "demo_task",
    "taskName": "示例平台任务",
    "taskGroup": "demo",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "requiredCapabilities": {"browser": False},
    "resourceRequirements": {},
}

@platform_task()
def run(context, **kwargs):
    context.logger.info("业务开始", event="business_started")
    return TaskResult.success("完成")
```

第二步，如果是接口型爬虫，在 `/open_api/<platform>/` 增加 API client。

第三步，同步并校验任务清单：

```bash
python scripts/sync_sch.py --write && python scripts/validate_tasks.py
```

第四步，生成 manifest 或走项目接入 CI：

```bash
python -m crawler_platform_spiders manifest
```

## 任务函数规范

推荐写法：

```python
from crawler_foundation.core.result import TaskResult
from spiders.common.decorators import platform_task

@platform_task()
def run(context, **kwargs):
    context.logger.info("业务开始", event="business_started")
    return TaskResult.success("完成", metrics={"count": 1})
```

平台 Agent 会调用：

```bash
python -m crawler_runtime --entrypoint spiders.xxx.yyy:run --kwargs-json '{}'
```

## 退出码规范

`@platform_task` 会把异常转换为标准 `TaskResult`，`crawler_runtime` 会把失败结果转换成非 0 进程退出码，确保平台 Agent 能正确识别失败。

```text
0  成功 / 跳过 / 部分成功
10 参数错误
20 配置错误
30 登录失败
40 验证码或风控
50 网络失败
60 数据库失败
70 业务无数据
80 解析失败
90 未知异常
```

## 生产目录约束

生产任务容器内请只写这些目录：

- `/work`：任务临时工作目录
- `/logs`：导出日志、附件和人工排查文件
- `/cache`：可复用缓存
- `/profiles`：浏览器 profile

不要写容器根目录。

## 上线前检查

```bash
python scripts/sync_sch.py --check && python scripts/validate_tasks.py && python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins && pytest -q
```

## 平台侧注意

crawler_platform Agent 应向任务容器注入完整运行上下文。当前基建已兼容 `CRAWLER_COMPANY_ID`，但如果平台 Agent 未注入公司 ID，业务任务只能从 payload 中读取，无法从容器内部自行恢复。

## Oilchem 平台规范样例

1.0.16 已按标准结构新增 Oilchem：

```text
spiders/oilchem/
  base.py      # 登录、session、headers、token/cookie 缓存
  login.py     # 独立登录校验任务 oilchem_login_check
```

本地校验 token/cookie：

```bash
python -m crawler_platform_spiders run --task-code oilchem_login_check --kwargs-json '{"username":"账号","token":"JWT_TOKEN"}'
```

或者：

```bash
python -m crawler_platform_spiders run --task-code oilchem_login_check --kwargs-json '{"account":{"username":"账号","cookieString":"_member_user_tonken_=...;refpay=0"}}'
```

1.0.16 开始支持按 HAR 复盘后的表单登录字段提交用户名密码，但必须额外传入网易易盾返回的 `NECaptchaValidate`：

```bash
python -m crawler_platform_spiders run --task-code oilchem_login_check --kwargs-json '{"account":{"username":"账号","password":"密码或32位MD5","captchaValidate":"网易易盾validate"},"persist":true}'
```

说明：`captchaValidate` 需要由浏览器、人工或合规打码服务提前取得。本基类不会在纯 requests 流程里伪造或绕过网易易盾。登录成功后会提取 `_member_user_tonken_`，并用 `dc.oilchem.net/ndc/common/getUserId` 做二次校验。

后续 Oilchem 新业务只新增 `spiders/oilchem/<业务名>.py`，业务模块调用 `OilchemBase.login()` 获取已校验 session，然后自行解析和入库。

## 与 crawler_platform 联通发布

1.0.16 开始，推荐使用“CI/CD 构建一次镜像，平台注册一次版本，多台 Agent 拉同一个 digest 执行”的模式，不再建议每台服务器分别 `git pull && docker build`。

本地或 CI 发布前复制配置：

```bash
cp .env.platform.example .env.platform
```

编辑 `.env.platform` 后执行：

```bash
bash scripts/build_and_register.sh
```

如果镜像已经由 CI 构建并取得 digest，可以只注册：

```bash
python scripts/platform_register.py --platform-url http://127.0.0.1:8000 --discovery-token xxx --company-id 1 --server-code agent-01 --image-repository registry.example.com/crawler_platform_spiders --image-digest sha256:0000000000000000000000000000000000000000000000000000000000000000 --release-version 1.0.16
```

多台设备执行时，代码和镜像仍然只发布一次。平台根据项目服务器池、任务指定服务器、Agent 标签、资源状态决定由哪台 Agent 拉取镜像并执行任务。

完整说明见：`docs/PLATFORM_INTEGRATION.md`。

## 1.0.16 账号状态公共组件

1.0.16 新增 `crawler_foundation.accounts`，爬虫代码可以通过 `context.accounts.report_success/report_failure` 或旧项目兼容函数 `report_account_status` 上报账号状态。公共组件不读取公司账号缓存库，只上报标准事件。详见 `docs/ACCOUNT_STATUS_STANDARD.md`。

## 1.0.16 爬虫项目标准契约 v1

1.0.16 开始，爬虫项目按 `TASK_DEFINITION.platformCode / requiredConfigs / requiredCredentials / outputTables` 声明任务契约。账号组合通过 `context.accounts.get/list/lease/resolve/affinity/external_affinity` 调用，支持固定账号、多账号、账号池、规则匹配、对象首次成功后绑定账号，以及兼容外部公司缓存 `credential_key` 字段。详见 `docs/SPIDER_PROJECT_CONTRACT_V1.md`。

## 1.0.16 爬虫开发标准库增强

1.0.16 开始推荐所有新任务使用 `spiders.common.standard` 作为统一导入入口，优先选择 `StandardPageTask`、`StandardSubjectTask`、`StandardApiBase` 三类模板。新增任务可以直接使用：

```bash
python scripts/create_task.py --platform demo --definition-key demo_company_query --task-name 公司查询 --task-kind subject --subject-type company --table-name demo_company_info
```

开发完成后执行：

```bash
python scripts/sync_sch.py --write && python scripts/validate_tasks.py
```

详见 `docs/SPIDER_DEVELOPMENT_STANDARD_1.0.13.md`。

## 1.0.16 外部 CI Release 注册标准

1.0.16 起，默认使用外部 CI 构建镜像并向 `crawler_platform` 注册 Release。平台构建中心未就绪时，不允许把 Git 仓库地址直接推进到平台内构建。

标准 workflow：

```text
.github/workflows/crawler-platform-spider-release.yml
```

项目归属建议写入：

```text
crawler_project.json.companyCode
```

可从示例复制：

```bash
cp crawler_project.example.json crawler_project.json
```

然后把 `companyCode` 改为平台公司编码，并在 GitHub Secrets/Variables 中配置：

```text
CRAWLER_CONTROL_BASE_URL
CRAWLER_DISCOVERY_TOKEN
CRAWLER_REGISTRY_HOST
CRAWLER_REGISTRY_NAMESPACE
CRAWLER_IMAGE_REPOSITORY
```

HTTP 私有镜像仓库需要额外设置：

```text
CRAWLER_REGISTRY_INSECURE=true
```

详见 `docs/EXTERNAL_CI_RELEASE_REGISTRATION_1.0.16.md`。
