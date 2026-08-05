from __future__ import annotations

from spiders.common.base import BaseSpider


class ApiSpider(BaseSpider):
    def http(self, alias: str = "default", **options):
        from plugins.http.session import create_session

        return create_session(**options)
