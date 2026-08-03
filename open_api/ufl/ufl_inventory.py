# -*- coding: utf-8 -*-
# @Time    : 2024/7/19 17:42
# @Author  : Haijun
# @Description :

import http.client
import json
import math
import ssl
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from openApi.ufl.base import UFLEplusssBase


def _today_yyyy_mm_dd() -> str:
    """
    Prefer Asia/Shanghai if zoneinfo is available; otherwise fall back to local time.
    """
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Shanghai")).date().strftime("%Y-%m-%d")
    return datetime.today().date().strftime("%Y-%m-%d")


class UFLEplusssInventory(UFLEplusssBase):
    """
    Inventory sync for UFreight Eplusss WMS.
    """

    def __init__(
            self,
            *args,
            verify_ssl: bool = False,
            timeout: int = 30,
            max_retries: int = 2,
            retry_backoff_sec: float = 0.8,
    ):
        super().__init__()
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_sec = retry_backoff_sec
        # self.wms_ufl_eplusss_inventory_old_table = "wms_ufl_eplusss_inventory"
        self.wms_ufl_eplusss_inventory_new_table = "wms_ufl_eplusss_inventory_new"
        # self.db.delete_data_from_table(self.wms_ufl_eplusss_inventory_old_table, where=f'dt="{_today_yyyy_mm_dd()}"')
        self.db.delete_data_from_table(self.wms_ufl_eplusss_inventory_new_table, where=f'dt="{_today_yyyy_mm_dd()}"')

        # If your environment requires bypassing verification, set verify_ssl=False.
        self._ssl_context = None
        if not self.verify_ssl:
            self._ssl_context = ssl._create_unverified_context()

    def _request_inventory(
            self,
            customer_code: str,
            warehouse_code: str,
            site: str,
            page: int = 1,
    ) -> Dict[str, Any]:
        """
        Request inventory page with basic retries and status checks.
        """
        headers = {
            "Authorization": f"Basic {self.auth()}",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        params = {
            "customer": customer_code,
            "warehouseCode": warehouse_code,
            "page": page,
            "pageSize": self.page_size,
        }
        path = f"/{site}/wosedi/ws/apiQueryInventory?{urlencode(params)}"

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            conn = None
            try:
                conn = http.client.HTTPSConnection(
                    "service.ufreight.com",
                    8443,
                    context=self._ssl_context,
                    timeout=self.timeout,
                )
                conn.request("GET", path, headers=headers)
                res = conn.getresponse()
                raw = res.read()

                if res.status < 200 or res.status >= 300:
                    # Keep a short snippet for debugging; avoid printing full payload.
                    snippet = (raw[:300] if raw else b"").decode("utf-8", errors="replace")
                    raise RuntimeError(f"HTTP {res.status} {res.reason}; body_snippet={snippet}")

                if not raw:
                    return {}

                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    snippet = raw[:300].decode("utf-8", errors="replace")
                    raise RuntimeError(f"JSON decode failed; body_snippet={snippet}") from e

            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_sec * (2 ** attempt))
                    continue
                raise
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Unreachable, but keeps type-checkers happy
        if last_err:
            raise last_err
        return {}

    def get_inventory(self, account_info: Dict[str, Any]) -> None:
        """
        Fetch all pages, aggregate by product_code, then upsert into DB.
        """
        warehouse_code = (account_info.get("warehouse_code") or "").strip()
        customer_code = (account_info.get("customer_code") or "").strip()
        site = (account_info.get("site") or "").strip()

        if not warehouse_code or not customer_code or not site:
            return

        item_dict: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        resp = self._request_inventory(customer_code, warehouse_code, site, page=1)
        self.parse_data(account_info, resp, item_dict)

        total_count = 0
        try:
            total_count = int(resp.get("data", {}).get("totalCount") or 0)
        except Exception:
            total_count = 0

        pages = max(1, math.ceil(total_count / max(1, int(self.page_size))))
        if pages > 1:
            for page in range(2, pages + 1):
                page_resp = self._request_inventory(customer_code, warehouse_code, site, page=page)
                self.parse_data(account_info, page_resp, item_dict)

        if not item_dict:
            return

        item_list: List[Dict[str, Any]] = []
        for code, product_list in item_dict.items():
            if not product_list:
                continue

            # Defensive sums
            total_stock = 0
            available_stock = 0
            for row in product_list:
                try:
                    total_stock += int(row.get("total_stock") or 0)
                except Exception:
                    pass
                try:
                    available_stock += int(row.get("available_stock") or 0)
                except Exception:
                    pass

            first = product_list[0]
            item_list.append(
                {
                    "dt": first.get("dt"),
                    "username": account_info.get("username"),
                    "product_code": first.get("product_code") or code,
                    "customer_code": first.get("customer_code"),
                    "product_detail": first.get("product_detail"),
                    "ex_date": first.get("ex_date"),
                    "status": first.get("status"),
                    "total_stock": total_stock,
                    "available_stock": available_stock,
                    "qty_unit": first.get("qty_unit"),
                    "warehouse_code": warehouse_code,
                }
            )

        # if item_list:
        #     self.db.batch_insert_replace(self.wms_ufl_eplusss_inventory_old_table, item_list)

    def parse_data(self, account_info, resp: Dict[str, Any], item_dict: Dict[str, List[Dict[str, Any]]]) -> None:
        data = (resp or {}).get("data") or {}
        part_list = data.get("PartInvList") or []
        if not part_list:
            return

        dt_str = _today_yyyy_mm_dd()

        new_item_list = []
        for row in part_list:
            qty_intent = row.get("qtyIntent") or 0
            qty_inv = row.get("qtyInv") or 0
            try:
                qty_intent_i = int(qty_intent)
            except Exception:
                qty_intent_i = 0
            try:
                qty_inv_i = int(qty_inv)
            except Exception:
                qty_inv_i = 0

            product_code = row.get("partNo")
            if not product_code:
                continue

            item = {
                "dt": dt_str,
                "product_code": product_code,
                "customer_code": row.get("custCode"),  # 客户编码
                "product_detail": row.get("partDesc"),  # 商品描述
                "ex_date": row.get("expirationDate"),  # 过期日期
                "status": row.get("invStatus"),  # 状态
                "total_stock": qty_inv_i,  # 总库存
                "available_stock": max(0, qty_inv_i - qty_intent_i),  # 可用库存（不允许负数）
                "qty_unit": row.get("qtyUnit"),  # 数量单位
            }
            new_item = {
                "dt": dt_str,
                "seq_id": row.get("seqId"),
                "username": account_info.get("username"),
                "warehouse_code": account_info.get("warehouse_code"),
                "product_code": product_code,
                "customer_code": row.get("custCode"),  # 客户编码
                "product_detail": row.get("partDesc"),  # 商品描述
                "ex_date": row.get("expirationDate"),  # 过期日期
                "status": row.get("invStatus"),  # 状态
                "qty_inv": qty_inv_i,
                "qty_intent": qty_intent_i,
                "qty_unit": row.get("qtyUnit"),  # 数量单位
            }
            new_item_list.append(new_item)

            # print(item)
            item_dict[str(product_code)].append(item)

        self.db.batch_insert_replace(self.wms_ufl_eplusss_inventory_new_table, new_item_list)


def wms_ufl_eplusss_inventory() -> None:
    u = UFLEplusssInventory()
    for account_info in getattr(u, "account_list", []) or []:
        u.get_inventory(account_info=account_info)


if __name__ == "__main__":
    wms_ufl_eplusss_inventory()
