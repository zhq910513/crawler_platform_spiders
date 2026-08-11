# 爬虫项目开发标准（crawler_platform_spiders 1.0.13）

本标准面向以后新增业务开发，目标是把常见重复代码沉到公共库：任务入口、账号获取、账号池租约、对象亲和绑定、API Token、批量入库、分页循环、登录态缓存、异常上报。

## 一、目录约定

推荐结构：

```text
spiders/
  平台编码/
    base.py
    业务任务.py
```

复杂平台允许继续拆分：

```text
spiders/
  平台编码/
    base.py
    auth.py
    client.py
    parsers.py
    tasks/
      业务任务.py
```

但入口必须稳定：

```python
def run(context, **kwargs):
    ...
```

## 二、统一导入入口

新业务优先从这里导入：

```python
from spiders.common.standard import StandardPageTask, StandardSubjectTask, StandardApiBase
```

这个入口已经统一导出账号对象、登录态对象、批量写入、标准异常和标准基类。

## 三、四类任务模板

### 1. 普通任务

```bash
python scripts/create_task.py --platform demo --definition-key demo_new_task --task-name 新任务
```

### 2. 分页采集任务

```bash
python scripts/create_task.py --platform demo --definition-key demo_page_task --task-name 分页采集 --task-kind page --table-name demo_page_table
```

业务只实现：

```python
def request_page(self, page): ...
def parse_page(self, response, page): ...
```

### 3. 对象亲和任务

适合“公司第一次用某账号成功查询后，后续必须继续用同一账号”的场景。

```bash
python scripts/create_task.py --platform demo --definition-key demo_company_query --task-name 公司查询 --task-kind subject --subject-type company --table-name demo_company_info
```

业务只实现：

```python
def iter_subjects(self): ...
def get_subject_key(self, subject): ...
def query_subject(self, subject, account): ...
```

### 4. API 任务

适合 JDL、飞书、平台开放接口等 appKey/appSecret/token 场景。

```bash
python scripts/create_task.py --platform jdl --definition-key jdl_order_query --task-name JDL订单查询 --task-kind api
```

业务从账号槽位读取 API 凭证：

```python
account = self.load_api_account("api")
auth = self.context.accounts.auth(account)
```

## 四、账号调用标准

```python
context.accounts.get("login")
context.accounts.list("shopAccounts")
context.accounts.lease("worker")
context.accounts.resolve("login", subject)
context.accounts.affinity("queryAccount", "company", company_id)
context.accounts.external_affinity("queryAccount", "company", company_id, current_credential_key, on_bind_success)
```

业务代码不直接读 Cookie/Token 存储库；只通过 `context.accounts` 获取本次运行允许使用的账号。

## 五、批量入库标准

分页和对象任务默认使用 `BatchWriter`，避免一次性把所有数据放进内存。

普通任务也可以手动使用：

```python
with self.batch_writer("table_name", method="replace", batch_size=200) as writer:
    for row in rows:
        writer.add(row)
```

## 六、登录态缓存标准

统一使用 `AuthCacheRecord`：

```python
from spiders.common.standard import AuthCacheRecord, AuthState

record = AuthCacheRecord(
    company_code="ulike",
    platform_code="jdl",
    credential_key="jdl_main",
    auth=AuthState(access_token="...", refresh_token="..."),
    auth_source="TOKEN_REFRESH",
    health_status="HEALTHY",
    login_status="AUTH_ACTIVE",
    status_code="TOKEN_OK",
)
```

日志里只能使用：

```python
record.safe_dict()
```

## 七、任务契约校验

每个任务必须有静态 `TASK_DEFINITION`。新增或修改后执行：

```bash
python scripts/sync_sch.py --write && python scripts/validate_tasks.py
```

`validate_tasks.py` 会检查：

```text
definitionKey / platformCode / entryModule / entryFunction
requiredConfigs 槽位
requiredCredentials 槽位和账号绑定模式
outputTables 槽位和写入方式
affinity_pool 是否声明 subjectType
入口函数是否存在且可调用
```

## 八、禁止事项

```text
禁止在业务代码硬编码账号、Cookie、Token、API Key
禁止业务代码绕过 context.config / context.accounts
禁止请求失败后静默 return None
禁止账号状态和对象绑定关系散落在多个业务脚本里
禁止新增任务后不同步 sch.py
```
