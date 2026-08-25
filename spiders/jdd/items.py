from __future__ import annotations

import copy
import time
from typing import Any

from crawler_foundation.core.exceptions import ConfigurationError, ParseError, StorageError
from crawler_foundation.core.result import TaskResult
from open_api.jdd.items_client import DEFAULT_ITEMS_ENDPOINT, JddItemsQuery, fetch_items_page
from spiders.common.decorators import platform_task
from spiders.jdd.base import JddBase

TASK_DEFINITION = {
    "definitionKey": "jdd_items_sync",
    "taskName": "京多多现货商品采集",
    "defaultParams": {
        "pageSize": 500,
        "pageNum": 1,
        "dryRun": False,
        "verifyTls": False,
        "keyword": "",
        "cities": "",
        "categoryId": "",
    },
    "suggestedCron": "",
    "executionMode": "SINGLE",
    "idempotencyPolicy": "IDEMPOTENT",
    "resourceRequirements": {},
    "requiredCapabilities": {"browser": False},
    "runtimeMode": "SHARED_ENV_ISOLATED",
    "taskGroup": "jdd",
    "taskMaxConcurrency": 1,
    "groupMaxConcurrency": 2,
    "exclusiveMode": False,
    "ioClass": "NORMAL",
    "shmSizeMb": 64,
    "logLimitMb": 50,
    "resourceLocks": [],
    "secretRefs": [],
    "allowOfflineRun": False,
    "offlinePolicy": {},
    "requiredConfigs": [
        {
            "slot": "mongo_jdd",
            "type": "MONGO",
            "description": "京多多商品结果库 MongoDB，由 crawler_platform 公司资源配置绑定并在运行时下发。",
            "required": True,
        }
    ],
    "requiredCredentials": [],
    "outputTables": [
        {
            "slot": "items",
            "defaultName": "jdd.items",
            "writeMethod": "upsert",
            "description": "京多多现货商品采集结果，唯一键 item_id。",
        }
    ],
}


def _safe_int(value: Any, default: int, *, min_value: int = 1, max_value: int = 500) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(result, max_value))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def transform_items(payload: dict[str, Any], *, spider_time: str | None = None) -> list[dict[str, Any]]:
    if payload.get("message") != "success":
        raise ParseError("京多多接口返回非 success", details={"message": payload.get("message")})
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ParseError("京多多接口 data 不是对象")
    items = data.get("items")
    if not isinstance(items, list):
        raise ParseError("京多多接口 data.items 不是列表")
    now = spider_time or time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    rows: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        if raw.get("id") in (None, ""):
            continue
        item = copy.deepcopy(raw)
        item_id = item.pop("id")
        item["item_id"] = item_id
        item["spider_time"] = now
        rows.append(item)
    return rows


@platform_task()
def run(
    context,
    pageSize: int = 500,
    pageNum: int = 1,
    dryRun: bool = False,
    verifyTls: bool = False,
    endpoint: str = "",
    keyword: str = "",
    cities: str = "",
    categoryId: str = "",
) -> TaskResult:
    page_size = _safe_int(pageSize, 500)
    page_num = _safe_int(pageNum, 1, max_value=1000000)
    query = JddItemsQuery(
        page_size=page_size,
        page_num=page_num,
        keyword=str(keyword or ""),
        cities=str(cities or ""),
        category_id=str(categoryId or ""),
    )
    context.logger.info("京多多商品采集开始", event="jdd_items_started", pageSize=page_size, pageNum=page_num, dryRun=_truthy(dryRun))
    payload = fetch_items_page(query, endpoint=endpoint or DEFAULT_ITEMS_ENDPOINT, verify_tls=_truthy(verifyTls))
    rows = transform_items(payload)
    if _truthy(dryRun):
        context.logger.info("京多多商品采集 dry-run 完成", event="jdd_items_dry_run", fetched=len(rows))
        return TaskResult.success("jdd items dry-run ok", metrics={"fetched": len(rows), "upserted": 0, "pageSize": page_size, "pageNum": page_num})

    sink = JddBase(context)
    try:
        written = sink.upsert_items(rows)
    except (ConfigurationError, StorageError):
        raise
    except Exception as exc:
        raise StorageError("京多多商品写入 MongoDB 失败", details={"rows": len(rows)}) from exc
    finally:
        sink.close()
    context.logger.info("京多多商品采集完成", event="jdd_items_finished", fetched=len(rows), upserted=written)
    return TaskResult.success("jdd items sync ok", metrics={"fetched": len(rows), "upserted": written, "pageSize": page_size, "pageNum": page_num})
