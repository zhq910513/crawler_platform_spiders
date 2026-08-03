from __future__ import annotations

import threading
from typing import Any

from crawler_platform_spiders.errors import ConfigurationError


class HttpClientRegistry:
    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._options: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def client(self, alias: str = "default", **options: Any) -> Any:
        with self._lock:
            existing = self._clients.get(alias)
            if existing is not None:
                if options and options != self._options[alias]:
                    raise ConfigurationError(
                        "HTTP.CLIENT_ALIAS_CONFLICT",
                        f"HTTP client alias '{alias}' was already created with different options",
                        details={"client_alias": alias},
                    )
                return existing
            import httpx

            defaults = {
                "timeout": httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0),
                "verify": True,
                "follow_redirects": True,
            }
            defaults.update(options)
            client = httpx.Client(**defaults)
            self._clients[alias] = client
            self._options[alias] = options.copy()
            return client

    def close(self) -> None:
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
            self._options.clear()
        for client in clients:
            client.close()
