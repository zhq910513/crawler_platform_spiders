from __future__ import annotations

from typing import Any

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session(*, timeout_seconds: float = 60.0, retries: int = 2, backoff_factor: float = 0.5, headers: dict[str, str] | None = None, proxies: dict[str, str] | None = None) -> Session:
    session = Session()
    retry = Retry(total=retries, connect=retries, read=retries, status=retries, backoff_factor=backoff_factor, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=None, raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if headers:
        session.headers.update(headers)
    if proxies:
        session.proxies.update(proxies)
    original_request = session.request

    def request(method: str, url: str, **kwargs: Any):
        kwargs.setdefault("timeout", timeout_seconds)
        return original_request(method, url, **kwargs)

    session.request = request  # type: ignore[method-assign]
    return session
