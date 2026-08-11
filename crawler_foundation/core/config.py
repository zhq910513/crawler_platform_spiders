from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crawler_foundation.core.logging import sanitize


def load_dotenv(path: str | Path = ".env") -> None:
    target = Path(path)
    if not target.exists():
        return
    for line in target.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, raw = value.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = raw.strip().strip('"').strip("'")


@dataclass(frozen=True, slots=True)
class AppConfig:
    log_level: str = "INFO"
    timezone: str = "Asia/Shanghai"

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(log_level=os.getenv("LOG_LEVEL", "INFO"), timezone=os.getenv("TZ", "Asia/Shanghai"))


@dataclass(slots=True)
class ConfigRef:
    slot: str
    value: Any = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def ref(self) -> str:
        if isinstance(self.value, str):
            return self.value
        return str(self.raw.get("configRef") or self.raw.get("config_ref") or self.raw.get("ref") or "")

    def as_dict(self) -> dict[str, Any]:
        if isinstance(self.value, dict):
            return dict(self.value)
        if self.raw:
            return dict(self.raw)
        return {"ref": self.ref}

    def safe_dict(self) -> dict[str, Any]:
        return sanitize(self.as_dict())


class RuntimeConfigResolver:
    """Resolve company/project/task runtime configs injected by crawler_platform.

    It deliberately does not read arbitrary local .env database credentials for business
    logic. The platform/Agent should inject only this run's config references or resolved
    runtime config via CRAWLER_CONFIG_JSON / task payload. For early migration phases this
    object can return references such as ``config:mysql_main``; real DB client factories can
    be registered by platform projects later without changing business task code.
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data or {}
        self.configs = self._normalize(self.data.get("configs") or self.data.get("config") or {})
        self.bindings = self._normalize(self.data.get("configBindings") or self.data.get("config_bindings") or {})

    @classmethod
    def from_env_payload(cls, payload: dict[str, Any] | None = None) -> "RuntimeConfigResolver":
        env_data: dict[str, Any] = {}
        raw = os.getenv("CRAWLER_CONFIG_JSON", "")
        if raw:
            try:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    env_data.update(loaded)
            except Exception:
                env_data["_parseError"] = "CRAWLER_CONFIG_JSON invalid"
        if isinstance(payload, dict):
            for key in ("configs", "config", "configBindings", "config_bindings"):
                if key in payload:
                    env_data[key] = payload[key]
        return cls(env_data)

    def _normalize(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        return {str(k): v for k, v in data.items()}

    def get(self, slot: str, default: Any = None) -> Any:
        if slot in self.configs:
            return self.configs[slot]
        if slot in self.bindings:
            return self.bindings[slot]
        if default is not None:
            return default
        raise KeyError(f"配置槽位不存在：{slot}")

    def ref(self, slot: str) -> ConfigRef:
        value = self.get(slot)
        return ConfigRef(slot=slot, value=value, raw=value if isinstance(value, dict) else {})

    def mysql(self, slot: str = "mysql_main") -> Any:
        return self.get(slot)

    def redis(self, slot: str = "redis_main") -> Any:
        return self.get(slot)

    def mongo(self, slot: str = "mongo_main") -> Any:
        return self.get(slot)

    def oss(self, slot: str = "oss_main") -> Any:
        return self.get(slot)

    def safe_dict(self) -> dict[str, Any]:
        return sanitize({"configs": self.configs, "configBindings": self.bindings})
