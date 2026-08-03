from __future__ import annotations

from typing import Any

from crawler_platform_spiders.errors import ConfigurationError


class SecretStore:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values.copy()

    def get(self, name: str) -> str:
        value = self._values.get(name)
        if not isinstance(value, str) or not value:
            raise ConfigurationError(
                "RUNTIME.SECRET_MISSING",
                f"Required secret is missing: {name}",
                details={"secret_name": name},
            )
        return value

    def optional(self, name: str | None) -> str | None:
        if not name:
            return None
        return self.get(name)
