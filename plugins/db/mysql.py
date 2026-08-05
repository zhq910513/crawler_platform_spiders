from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import re
from typing import Any, Iterable, Iterator

from crawler_foundation.core.exceptions import DatabaseError
from crawler_foundation.core.retry import retry_call


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_identifier(name: str, *, allow_dot: bool = True) -> str:
    value = str(name or "").strip()
    if not value:
        raise DatabaseError("MySQL 标识符不能为空")
    parts = value.split(".") if allow_dot else [value]
    if not allow_dot and "." in value:
        raise DatabaseError("MySQL 字段名不能包含点号", details={"identifier": value})
    for part in parts:
        if not _IDENTIFIER_RE.fullmatch(part):
            raise DatabaseError("MySQL 标识符包含非法字符", details={"identifier": value})
    return ".".join(f"`{part}`" for part in parts)


def _quote_column(name: str) -> str:
    return _quote_identifier(name, allow_dot=False)


@dataclass(slots=True)
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    connect_timeout: int = 8
    read_timeout: int = 120
    write_timeout: int = 120


class MySQLClient:
    def __init__(self, config: MySQLConfig) -> None:
        self.config = config
        self._conn: Any | None = None

    def connect(self):
        if self._conn is not None:
            try:
                self._conn.ping(reconnect=True)
                return self._conn
            except Exception:
                self.close()
        try:
            import pymysql

            self._conn = pymysql.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset=self.config.charset,
                connect_timeout=self.config.connect_timeout,
                read_timeout=self.config.read_timeout,
                write_timeout=self.config.write_timeout,
                autocommit=False,
                cursorclass=pymysql.cursors.DictCursor,
            )
            return self._conn
        except Exception as exc:
            raise DatabaseError("MySQL 连接失败", details={"host": self.config.host, "database": self.config.database}) from exc

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        conn = self.connect()
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def fetch_all(self, sql: str, params: tuple[Any, ...] | dict[str, Any] | None = None) -> list[dict[str, Any]]:
        def op():
            with self.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

        return retry_call(op, attempts=2, retry_on=(Exception,), before_sleep=lambda *_: self.close())

    def execute(self, sql: str, params: tuple[Any, ...] | dict[str, Any] | None = None) -> int:
        def op():
            conn = self.connect()
            try:
                with conn.cursor() as cur:
                    count = cur.execute(sql, params)
                conn.commit()
                return int(count)
            except Exception:
                conn.rollback()
                raise

        return retry_call(op, attempts=2, retry_on=(Exception,), before_sleep=lambda *_: self.close())

    def executemany(self, sql: str, rows: Iterable[tuple[Any, ...] | dict[str, Any]]) -> int:
        data = list(rows)
        if not data:
            return 0
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                count = cur.executemany(sql, data)
            conn.commit()
            return int(count)
        except Exception as exc:
            conn.rollback()
            raise DatabaseError("MySQL 批量写入失败", details={"rows": len(data)}) from exc

    def insert_rows(self, table: str, rows: Iterable[dict[str, Any]], *, mode: str = "insert") -> int:
        """通用批量入库。

        业务任务自己决定入库表名，但表名和字段名必须是安全标识符。
        mode 支持：insert / replace / insert_ignore。
        """

        data = [dict(row) for row in rows]
        if not data:
            return 0
        columns = list(data[0].keys())
        if not columns:
            return 0
        for index, row in enumerate(data, start=1):
            if set(row.keys()) != set(columns):
                raise DatabaseError("MySQL 批量入库字段不一致", details={"rowIndex": index})
        normalized_mode = mode.lower().strip()
        verb_map = {"insert": "INSERT", "replace": "REPLACE", "insert_ignore": "INSERT IGNORE"}
        if normalized_mode not in verb_map:
            raise DatabaseError("MySQL 入库模式不支持", details={"mode": mode})
        table_sql = _quote_identifier(table)
        column_sql = ", ".join(_quote_column(col) for col in columns)
        value_sql = ", ".join(f"%({col})s" for col in columns)
        sql = f"{verb_map[normalized_mode]} INTO {table_sql} ({column_sql}) VALUES ({value_sql})"
        return self.executemany(sql, data)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
