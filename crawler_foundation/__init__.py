from __future__ import annotations

from pathlib import Path

APP_NAME = "crawler_platform_spiders"


def _read_version() -> str:
    for path in (Path(__file__).resolve().parents[1] / "VERSION",):
        try:
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            pass
    return "1.0.18"


__version__ = _read_version()

__all__ = ["APP_NAME", "__version__"]
