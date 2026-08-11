from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def iter_batches(items: Iterable[T], batch_size: int = 200) -> Iterator[list[T]]:
    """Yield non-empty batches without loading the whole iterable.

    Business tasks should use this for long paginated jobs instead of building one
    giant list in memory.  A batch size <= 0 is treated as 1 to avoid accidental
    infinite loops or empty flushes.
    """

    size = max(1, int(batch_size or 1))
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with string keys and without unsupported keys.

    The helper intentionally keeps ``None`` values because many spider tables use
    REPLACE/UPSERT semantics and need NULL to clear obsolete values.
    """

    return {str(key): value for key, value in row.items() if key not in (None, "")}


def normalize_rows(rows: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not rows:
        return []
    return [compact_row(row) for row in rows if isinstance(row, dict) and row]


class BatchWriter:
    """Small buffered writer used by standard tasks.

    ``write_func`` receives ``list[dict]``. It can be ``self.save_rows`` from a
    spider base class or any project-specific persistence function.
    """

    def __init__(self, write_func: Callable[[list[dict[str, Any]]], Any], *, batch_size: int = 200) -> None:
        self.write_func = write_func
        self.batch_size = max(1, int(batch_size or 1))
        self._buffer: list[dict[str, Any]] = []
        self.total_written = 0

    def add(self, row: dict[str, Any] | None) -> None:
        if not row:
            return
        self._buffer.append(compact_row(row))
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def extend(self, rows: Iterable[dict[str, Any]] | None) -> None:
        if not rows:
            return
        for row in rows:
            self.add(row)

    def flush(self) -> int:
        if not self._buffer:
            return 0
        rows = self._buffer
        self._buffer = []
        self.write_func(rows)
        self.total_written += len(rows)
        return len(rows)

    def close(self) -> int:
        return self.flush()

    def __enter__(self) -> "BatchWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if exc_type is None:
            self.flush()
