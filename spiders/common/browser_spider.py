from __future__ import annotations

from spiders.common.base import BaseSpider


class BrowserSpider(BaseSpider):
    @property
    def profile_dir(self):
        return self.context.dirs.profiles / self.context.task_code
