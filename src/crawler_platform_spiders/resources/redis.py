from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from crawler_platform_spiders.errors import ConfigurationError, InfrastructureError
from crawler_platform_spiders.models import RedisResources
from crawler_platform_spiders.resources.secrets import SecretStore


@dataclass(frozen=True, slots=True)
class RedisHandle:
    client: Any
    key_prefix: str

    def key(self, value: str) -> str:
        return f"{self.key_prefix}{value}"


class RedisRegistry:
    def __init__(self, config: RedisResources, secrets: SecretStore) -> None:
        self._config = config
        self._secrets = secrets
        self._handles: dict[str, RedisHandle] = {}
        self._lock = threading.Lock()

    def __getitem__(self, alias: str) -> RedisHandle:
        connection = self._config.connections.get(alias)
        if connection is None:
            raise ConfigurationError(
                "REDIS.CONNECTION_ALIAS_NOT_FOUND",
                f"Unknown Redis connection alias: {alias}",
                details={"connection_alias": alias},
            )
        with self._lock:
            existing = self._handles.get(alias)
            if existing is not None:
                return existing
            try:
                import redis

                pool = redis.ConnectionPool(
                    host=connection.host,
                    port=connection.port,
                    db=connection.database,
                    username=connection.username,
                    password=self._secrets.optional(connection.password_secret),
                    max_connections=connection.max_connections,
                    socket_connect_timeout=connection.socket_connect_timeout_seconds,
                    socket_timeout=connection.socket_timeout_seconds,
                    decode_responses=True,
                    ssl=connection.ssl,
                )
                handle = RedisHandle(redis.Redis(connection_pool=pool), connection.key_prefix)
                self._handles[alias] = handle
                return handle
            except ConfigurationError:
                raise
            except BaseException as exc:
                raise InfrastructureError(
                    "REDIS.CLIENT_CREATE_FAILED",
                    f"Failed to create Redis client for alias '{alias}'",
                    retryable=True,
                    details={"connection_alias": alias},
                ) from exc

    def close(self) -> None:
        with self._lock:
            handles = list(self._handles.values())
            self._handles.clear()
        for handle in handles:
            handle.client.close()
            handle.client.connection_pool.disconnect()
