from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crawler_foundation.core.context import TaskContext
from crawler_foundation.core.result import TaskResult


@dataclass(slots=True)
class BaseSpider:
    context: TaskContext

    @property
    def logger(self):
        return self.context.logger

    def run(self, **kwargs: Any) -> TaskResult:
        raise NotImplementedError
