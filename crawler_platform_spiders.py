"""Compatibility entry module for local commands.

The project root is named ``crawler_platform_spiders``.  The reusable Python
foundation package is intentionally named ``crawler_foundation`` so extracted
archives no longer contain ``crawler_platform_spiders/crawler_platform_spiders``.
This module preserves the convenient command:

    python -m crawler_platform_spiders manifest
"""
from __future__ import annotations

from crawler_foundation import __version__
from crawler_foundation.cli import main

__all__ = ["__version__", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
