from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

from crawler_platform_spiders import APP_NAME


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class TaskSpec(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_name: Literal[APP_NAME] = APP_NAME
    company_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=160)
    task_name: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9_]+(?:\.[a-z0-9_]+)+$")
    attempt: PositiveInt = 1
    max_attempts: PositiveInt = 1
    timeout_seconds: PositiveInt = Field(default=3600, le=604800)
    triggered_by: Literal["schedule", "manual", "retry", "api", "system"] = "system"
    triggered_by_user_id: str | None = Field(default=None, max_length=128)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value: Any) -> Any:
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    @model_validator(mode="after")
    def validate_attempts(self) -> "TaskSpec":
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot be greater than max_attempts")
        return self


class MySQLConnectionConfig(StrictModel):
    host: str = Field(min_length=1)
    port: int = Field(default=3306, ge=1, le=65535)
    username: str = Field(min_length=1)
    password_secret: str = Field(min_length=1)
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=5, ge=0, le=100)
    pool_timeout_seconds: int = Field(default=15, ge=1, le=300)
    pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    connect_timeout_seconds: int = Field(default=8, ge=1, le=300)
    read_timeout_seconds: int = Field(default=120, ge=1, le=3600)
    write_timeout_seconds: int = Field(default=120, ge=1, le=3600)


class MySQLDatabaseConfig(StrictModel):
    connection: str = Field(min_length=1)
    database: str = Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$")
    charset: str = Field(default="utf8mb4", pattern=r"^[A-Za-z0-9_-]+$")


class MySQLTableConfig(StrictModel):
    database: str = Field(min_length=1)
    table: str = Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$")


class MySQLResources(StrictModel):
    connections: dict[str, MySQLConnectionConfig] = Field(default_factory=dict)
    databases: dict[str, MySQLDatabaseConfig] = Field(default_factory=dict)
    tables: dict[str, MySQLTableConfig] = Field(default_factory=dict)


class MongoConnectionConfig(StrictModel):
    uri_secret: str = Field(min_length=1)
    min_pool_size: int = Field(default=0, ge=0, le=100)
    max_pool_size: int = Field(default=20, ge=1, le=500)
    connect_timeout_ms: int = Field(default=8000, ge=100, le=300000)
    server_selection_timeout_ms: int = Field(default=8000, ge=100, le=300000)

    @model_validator(mode="after")
    def validate_pool(self) -> "MongoConnectionConfig":
        if self.min_pool_size > self.max_pool_size:
            raise ValueError("min_pool_size cannot exceed max_pool_size")
        return self


class MongoDatabaseConfig(StrictModel):
    connection: str = Field(min_length=1)
    database: str = Field(min_length=1)


class MongoCollectionConfig(StrictModel):
    database: str = Field(min_length=1)
    collection: str = Field(min_length=1)


class MongoResources(StrictModel):
    connections: dict[str, MongoConnectionConfig] = Field(default_factory=dict)
    databases: dict[str, MongoDatabaseConfig] = Field(default_factory=dict)
    collections: dict[str, MongoCollectionConfig] = Field(default_factory=dict)


class RedisConnectionConfig(StrictModel):
    host: str = Field(min_length=1)
    port: int = Field(default=6379, ge=1, le=65535)
    database: int = Field(default=0, ge=0, le=1024)
    username: str | None = None
    password_secret: str | None = None
    key_prefix: str = ""
    max_connections: int = Field(default=10, ge=1, le=500)
    socket_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=300)
    socket_timeout_seconds: float = Field(default=30.0, gt=0, le=3600)
    ssl: bool = False


class RedisResources(StrictModel):
    connections: dict[str, RedisConnectionConfig] = Field(default_factory=dict)


class ResourceManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    company_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    mysql: MySQLResources = Field(default_factory=MySQLResources)
    mongo: MongoResources = Field(default_factory=MongoResources)
    redis: RedisResources = Field(default_factory=RedisResources)

    @model_validator(mode="after")
    def validate_references(self) -> "ResourceManifest":
        for alias, database in self.mysql.databases.items():
            if database.connection not in self.mysql.connections:
                raise ValueError(f"mysql database '{alias}' references unknown connection '{database.connection}'")
        for alias, table in self.mysql.tables.items():
            if table.database not in self.mysql.databases:
                raise ValueError(f"mysql table '{alias}' references unknown database '{table.database}'")
        for alias, database in self.mongo.databases.items():
            if database.connection not in self.mongo.connections:
                raise ValueError(f"mongo database '{alias}' references unknown connection '{database.connection}'")
        for alias, collection in self.mongo.collections.items():
            if collection.database not in self.mongo.databases:
                raise ValueError(f"mongo collection '{alias}' references unknown database '{collection.database}'")
        return self


class ResultStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ErrorInfo(StrictModel):
    code: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    retryable: bool = False
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)
    traceback: str | None = None


class TaskResult(StrictModel):
    status: ResultStatus
    message: str = Field(min_length=1, max_length=4000)
    metrics: dict[str, int | float | str | bool | None] = Field(default_factory=dict)
    error: ErrorInfo | None = None

    @classmethod
    def success(cls, message: str, *, metrics: dict[str, Any] | None = None) -> "TaskResult":
        return cls(status=ResultStatus.SUCCESS, message=message, metrics=metrics or {})

    @classmethod
    def partial_success(cls, message: str, *, metrics: dict[str, Any] | None = None) -> "TaskResult":
        return cls(status=ResultStatus.PARTIAL_SUCCESS, message=message, metrics=metrics or {})

    @classmethod
    def skipped(cls, message: str, *, metrics: dict[str, Any] | None = None) -> "TaskResult":
        return cls(status=ResultStatus.SKIPPED, message=message, metrics=metrics or {})

    @classmethod
    def failed(
        cls,
        message: str,
        *,
        error: ErrorInfo | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> "TaskResult":
        return cls(status=ResultStatus.FAILED, message=message, metrics=metrics or {}, error=error)


class FinalResult(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_name: Literal[APP_NAME] = APP_NAME
    release_version: str
    build_sha: str
    image_digest: str | None = None
    company_id: str
    project_id: str
    task_id: str
    run_id: str
    task_name: str
    attempt: int
    status: ResultStatus
    exit_code: int
    message: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    metrics: dict[str, int | float | str | bool | None] = Field(default_factory=dict)
    last_error: ErrorInfo | None = None
    terminal_error: ErrorInfo | None = None
