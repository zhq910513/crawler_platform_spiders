from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def loads_dict(value: str | None, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    return loads_object(value, default=default)


def loads_object(value: str | None, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not value:
        return {} if default is None else default
    result = json.loads(value)
    if not isinstance(result, dict):
        raise TypeError("JSON value must be an object")
    return result


def loads_list(value: str | None, *, default: list[Any] | None = None) -> list[Any]:
    if not value:
        return [] if default is None else default
    result = json.loads(value)
    if not isinstance(result, list):
        raise TypeError("JSON value must be a list")
    return result


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
