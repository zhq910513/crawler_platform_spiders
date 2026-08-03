from __future__ import annotations

import threading
from typing import Any

from crawler_platform_spiders.errors import ConfigurationError, InfrastructureError
from crawler_platform_spiders.models import MongoResources
from crawler_platform_spiders.resources.secrets import SecretStore


class MongoRegistry:
    def __init__(self, config: MongoResources, secrets: SecretStore) -> None:
        self._config = config
        self._secrets = secrets
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()

    def client(self, connection_alias: str) -> Any:
        connection = self._config.connections.get(connection_alias)
        if connection is None:
            raise ConfigurationError(
                "MONGO.CONNECTION_ALIAS_NOT_FOUND",
                f"Unknown MongoDB connection alias: {connection_alias}",
                details={"connection_alias": connection_alias},
            )
        with self._lock:
            existing = self._clients.get(connection_alias)
            if existing is not None:
                return existing
            try:
                from pymongo import MongoClient

                client = MongoClient(
                    self._secrets.get(connection.uri_secret),
                    minPoolSize=connection.min_pool_size,
                    maxPoolSize=connection.max_pool_size,
                    connectTimeoutMS=connection.connect_timeout_ms,
                    serverSelectionTimeoutMS=connection.server_selection_timeout_ms,
                )
                self._clients[connection_alias] = client
                return client
            except ConfigurationError:
                raise
            except BaseException as exc:
                raise InfrastructureError(
                    "MONGO.CLIENT_CREATE_FAILED",
                    f"Failed to create MongoDB client for alias '{connection_alias}'",
                    retryable=True,
                    details={"connection_alias": connection_alias},
                ) from exc

    def database(self, database_alias: str) -> Any:
        database = self._config.databases.get(database_alias)
        if database is None:
            raise ConfigurationError(
                "MONGO.DATABASE_ALIAS_NOT_FOUND",
                f"Unknown MongoDB database alias: {database_alias}",
                details={"database_alias": database_alias},
            )
        return self.client(database.connection)[database.database]

    def collection(self, collection_alias: str) -> Any:
        collection = self._config.collections.get(collection_alias)
        if collection is None:
            raise ConfigurationError(
                "MONGO.COLLECTION_ALIAS_NOT_FOUND",
                f"Unknown MongoDB collection alias: {collection_alias}",
                details={"collection_alias": collection_alias},
            )
        return self.database(collection.database)[collection.collection]

    def close(self) -> None:
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            client.close()
