from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def atomic_write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, separators=(",", ":"), default=str)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, target)
    except BaseException:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise
