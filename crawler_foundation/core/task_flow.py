from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from crawler_foundation.accounts import AccountCredential
from crawler_foundation.core.batch import BatchWriter, normalize_rows
from crawler_foundation.core.result import TaskResult
from crawler_foundation.core.standard_base import StandardPlatformBase


class StandardBusinessTask(StandardPlatformBase):
    """Recommended base for new business tasks.

    Subclasses normally implement ``iter_rows`` and set ``default_table_name``.
    The base handles batching, writing and a consistent TaskResult.
    """

    default_table_name = ""
    default_table_slot = "detailTable"
    default_write_method = "replace"
    default_batch_size = 200

    def get_table_name(self, slot: str | None = None, default: str | None = None) -> str:
        slot = slot or self.default_table_slot
        default_name = default if default is not None else self.default_table_name
        return str(self.params.get(slot) or self.params.get("tableName") or default_name or "")

    def iter_rows(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError

    def write_rows(self, rows: list[dict[str, Any]]) -> None:
        table = self.get_table_name()
        if not table:
            raise RuntimeError("未配置输出表名，请设置 default_table_name 或任务参数 tableName")
        self.save_rows(table, normalize_rows(rows), method=self.default_write_method)

    def run(self) -> TaskResult:
        with BatchWriter(self.write_rows, batch_size=int(self.params.get("batchSize") or self.default_batch_size)) as writer:
            for row in self.iter_rows():
                writer.add(row)
        return TaskResult.success("任务执行完成", metrics={"rows": writer.total_written})


class StandardPageTask(StandardBusinessTask):
    """Recommended base for page/cursor based list crawlers."""

    start_page = 1
    max_pages_param = "maxPages"

    def request_page(self, page: int) -> Any:
        raise NotImplementedError

    def parse_page(self, response: Any, page: int) -> tuple[list[dict[str, Any]], bool]:
        raise NotImplementedError

    def iter_rows(self) -> Iterator[dict[str, Any]]:
        page = int(self.params.get("startPage") or self.start_page)
        max_pages = int(self.params.get(self.max_pages_param) or 0)
        seen = 0
        while True:
            response = self.request_page(page)
            rows, has_next = self.parse_page(response, page)
            for row in rows:
                yield row
            seen += 1
            if not has_next:
                break
            if max_pages and seen >= max_pages:
                break
            page += 1


class StandardSubjectTask(StandardBusinessTask):
    """Recommended base for object-centric tasks such as company/shop queries."""

    subject_type = "subject"
    account_slot = "queryAccount"

    def iter_subjects(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError

    def get_subject_key(self, subject: dict[str, Any]) -> str:
        return str(subject.get("subjectKey") or subject.get("company_id") or subject.get("companyId") or subject.get("id") or "")

    def get_subject_meta(self, subject: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in subject.items() if key not in {"cookie", "token", "password", "authorization"}}

    def query_subject(self, subject: dict[str, Any], account: AccountCredential) -> dict[str, Any] | list[dict[str, Any]] | None:
        raise NotImplementedError

    def iter_rows(self) -> Iterator[dict[str, Any]]:
        for subject in self.iter_subjects():
            subject_key = self.get_subject_key(subject)
            if not subject_key:
                self.logger.warning("业务对象缺少唯一键，已跳过", event="subject_key_missing")
                continue
            with self.context.accounts.affinity(
                self.account_slot,
                self.subject_type,
                subject_key,
                self.get_subject_meta(subject),
                self.context.payload,
            ) as account:
                result = self.query_subject(subject, account)
            if isinstance(result, dict):
                yield result
            elif isinstance(result, list):
                for row in result:
                    if isinstance(row, dict):
                        yield row
