from __future__ import annotations

from datetime import date, datetime
from typing import Any


def to_date_string(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return ""
    return datetime.fromisoformat(text.replace("/", "-")).date().isoformat()
