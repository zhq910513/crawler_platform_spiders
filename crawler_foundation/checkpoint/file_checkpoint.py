from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FileCheckpoint:
    """Small local checkpoint helper for platform tasks.

    It is intentionally simple and dependency-free. Production tasks may later
    swap this with MySQL/Redis checkpoint backends while keeping the same
    load/save/mark_done contract.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    def load(self, key: str, default: Any = None) -> Any:
        return self.load_all().get(key, default)

    def save(self, key: str, value: Any) -> None:
        data = self.load_all()
        data[key] = value
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def mark_done(self, value: bool = True) -> None:
        self.save("done", bool(value))
