# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from crawler_foundation.core.context import TaskContext
from crawler_foundation.core.result import TaskResult
from plugins.db.mysql import MySQLClient, MySQLConfig
from spiders.common.decorators import platform_task
from spiders.oilchem.base import OilchemAccount, OilchemBase

"""Oilchem 业务任务模板。

后续真实业务请按这个结构复制为 `业务名.py`：
1. 账号信息由任务参数传入，不在代码硬编码。
2. 登录、session、headers、cookie/token 缓存统一调用 base.py。
3. 业务模块只负责接口请求、解析、字段 mapping 和入库表选择。
4. 本文件没有 TASK_DEFINITION，不会被平台导入；真实任务要声明自己的 TASK_DEFINITION。
"""


@platform_task()
def run(context: TaskContext, *, table: str, rows: list[dict[str, Any]] | None = None, account: dict[str, Any] | None = None) -> TaskResult:
    oilchem_account = OilchemAccount.from_payload(context.payload, account=account or {})
    spider = OilchemBase(context, account=oilchem_account)
    try:
        login_data = spider.login(oilchem_account, check=True, persist=True)
        # 示例：业务自行决定表名；生产任务需要从环境变量或参数构造 MySQLConfig。
        # db = MySQLClient(MySQLConfig(host="...", port=3306, user="...", password="...", database="..."))
        # affected = db.insert_rows(table, rows or [], mode="replace")
        affected = 0
        return TaskResult.success("oilchem 业务模板执行成功", metrics={"affectedRows": affected}, data={"login": login_data, "targetTable": table})
    finally:
        spider.close()
