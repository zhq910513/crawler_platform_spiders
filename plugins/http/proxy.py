from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    http: str = ""
    https: str = ""

    def to_requests(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if self.http:
            result["http"] = self.http
        if self.https:
            result["https"] = self.https
        return result
