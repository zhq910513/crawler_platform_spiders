from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from crawler_platform_spiders.errors import ConfigurationError, InfrastructureError
from crawler_platform_spiders.models import MySQLResources
from crawler_platform_spiders.resources.secrets import SecretStore


@dataclass(frozen=True, slots=True)
class MySQLTableRef:
    alias: str
    database_alias: str
    database_name: str
    table_name: str

    @property
    def qualified_name(self) -> str:
        return f"`{self.database_name}`.`{self.table_name}`"


class MySQLRegistry:
    def __init__(self, config: MySQLResources, secrets: SecretStore) -> None:
        self._config = config
        self._secrets = secrets
        self._engines: dict[str, Any] = {}
        self._lock = threading.Lock()

    def engine(self, database_alias: str) -> Any:
        if database_alias not in self._config.databases:
            raise ConfigurationError(
                "MYSQL.DATABASE_ALIAS_NOT_FOUND",
                f"Unknown MySQL database alias: {database_alias}",
                details={"database_alias": database_alias},
            )
        with self._lock:
            existing = self._engines.get(database_alias)
            if existing is not None:
                return existing
            try:
                from sqlalchemy import URL, create_engine

                database = self._config.databases[database_alias]
                connection = self._config.connections[database.connection]
                url = URL.create(
                    "mysql+pymysql",
                    username=connection.username,
                    password=self._secrets.get(connection.password_secret),
                    host=connection.host,
                    port=connection.port,
                    database=database.database,
                    query={"charset": database.charset},
                )
                engine = create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_size=connection.pool_size,
                    max_overflow=connection.max_overflow,
                    pool_timeout=connection.pool_timeout_seconds,
                    pool_recycle=connection.pool_recycle_seconds,
                    connect_args={
                        "connect_timeout": connection.connect_timeout_seconds,
                        "read_timeout": connection.read_timeout_seconds,
                        "write_timeout": connection.write_timeout_seconds,
                    },
                )
                self._engines[database_alias] = engine
                return engine
            except ConfigurationError:
                raise
            except BaseException as exc:
                raise InfrastructureError(
                    "MYSQL.ENGINE_CREATE_FAILED",
                    f"Failed to create MySQL engine for alias '{database_alias}'",
                    retryable=True,
                    details={"database_alias": database_alias},
                ) from exc

    def table(self, table_alias: str) -> MySQLTableRef:
        table = self._config.tables.get(table_alias)
        if table is None:
            raise ConfigurationError(
                "MYSQL.TABLE_ALIAS_NOT_FOUND",
                f"Unknown MySQL table alias: {table_alias}",
                details={"table_alias": table_alias},
            )
        database = self._config.databases[table.database]
        return MySQLTableRef(table_alias, table.database, database.database, table.table)

    def close(self) -> None:
        with self._lock:
            engines = list(self._engines.values())
            self._engines.clear()
        for engine in engines:
            engine.dispose()
