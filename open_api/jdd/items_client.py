from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from plugins.http.session import create_session

DEFAULT_ITEMS_ENDPOINT = "https://testapi.jduoduo.com/api/search/ESSpot/esSpotQueryPage"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Host": "testapi.jduoduo.com",
    "Origin": "https://www.ejzy.cn",
    "Pragma": "no-cache",
    "Referer": "https://www.ejzy.cn/",
    "sec-ch-ua": '"Google Chrome";v="105", "Not)A;Brand";v="8", "Chromium";v="105"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "systemFlag": "jduoduo",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
}


@dataclass(frozen=True, slots=True)
class JddItemsQuery:
    page_size: int = 500
    page_num: int = 1
    if_attention: bool = True
    show_seven_days: int = 1
    show_days_num: int = 3
    quotation_sort: int = 2
    keyword: str = ""
    cities: str = ""
    category_id: str = ""


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def build_items_url(query: JddItemsQuery, *, endpoint: str = DEFAULT_ITEMS_ENDPOINT) -> str:
    params = {
        "defaultRecommendation": "0",
        "pageSize": str(max(1, min(int(query.page_size or 1), 500))),
        "ifAttention": _bool_text(bool(query.if_attention)),
        "showSevenDays": str(query.show_seven_days),
        "showDaysNum": str(query.show_days_num),
        "pageNum": str(max(1, int(query.page_num or 1))),
        "cities": query.cities,
        "allGoods": "",
        "categoryId": query.category_id,
        "keyword": query.keyword,
        # 保留原始案例里的参数名，避免擅自改动远端接口契约。
        "rocessingLevelList": "",
        "manufacturerList": "",
        "quotationSort": str(query.quotation_sort),
        "inputPrice": "",
        "deliveryStart": "",
        "deliveryDeadline": "",
        "onSale": "",
        "saleMode": "",
    }
    return f"{endpoint}?{urlencode(params)}"


def fetch_items_page(
    query: JddItemsQuery,
    *,
    session: Any | None = None,
    endpoint: str = DEFAULT_ITEMS_ENDPOINT,
    timeout_seconds: float = 30.0,
    verify_tls: bool = False,
) -> dict[str, Any]:
    if not verify_tls:
        try:
            import requests

            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
        except Exception:
            pass
    client = session or create_session(timeout_seconds=timeout_seconds, retries=2, headers=DEFAULT_HEADERS)
    response = client.get(build_items_url(query, endpoint=endpoint), headers=DEFAULT_HEADERS, verify=verify_tls)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise TypeError("京多多接口返回不是 JSON 对象")
    return data
