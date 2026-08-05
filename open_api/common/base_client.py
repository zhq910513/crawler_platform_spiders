from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crawler_foundation.core.exceptions import NetworkError
from plugins.http.session import create_session


@dataclass(slots=True)
class BaseOpenApiClient:
    base_url: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        self.session = create_session(timeout_seconds=self.timeout_seconds)
        if self.headers:
            self.session.headers.update(self.headers)

    def request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        try:
            response = self.session.request(method.upper(), url, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise NetworkError(f"接口请求失败：{url}", details={"url": url, "method": method}) from exc
