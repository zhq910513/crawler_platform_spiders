from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_call(func: Callable[[], T], *, attempts: int = 3, delay_seconds: float = 1.0, backoff: float = 2.0, jitter_seconds: float = 0.2, retry_on: tuple[type[BaseException], ...] = (Exception,), should_retry: Callable[[BaseException], bool] | None = None, before_sleep: Callable[[int, BaseException, float], None] | None = None) -> T:
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    current_delay = max(0.0, delay_seconds)
    last_error: BaseException | None = None
    for index in range(1, attempts + 1):
        try:
            return func()
        except retry_on as exc:
            last_error = exc
            if index >= attempts or (should_retry and not should_retry(exc)):
                raise
            sleep_seconds = current_delay + random.uniform(0, max(0.0, jitter_seconds))
            if before_sleep:
                before_sleep(index, exc, sleep_seconds)
            time.sleep(sleep_seconds)
            current_delay *= backoff
    raise last_error or RuntimeError("retry failed without captured error")
