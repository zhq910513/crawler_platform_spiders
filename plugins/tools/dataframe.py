from __future__ import annotations

from typing import Any


def rows_to_dicts(rows: Any) -> list[dict]:
    try:
        return rows.fillna("").to_dict(orient="records")
    except AttributeError:
        return [dict(item) for item in rows]
