from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
