from __future__ import annotations

import threading
from collections.abc import Callable

from crawler_platform_spiders.errors import ConfigurationError
from crawler_platform_spiders.models import ResourceManifest
from crawler_platform_spiders.resources.http import HttpClientRegistry
from crawler_platform_spiders.resources.mongo import MongoRegistry
from crawler_platform_spiders.resources.mysql import MySQLRegistry
from crawler_platform_spiders.resources.redis import RedisRegistry
from crawler_platform_spiders.resources.secrets import SecretStore


class ResourceManager:
    def __init__(self, manifest: ResourceManifest, secrets: SecretStore) -> None:
        self.manifest = manifest
        self.secrets = secrets
        self.mysql = MySQLRegistry(manifest.mysql, secrets)
        self.mongo = MongoRegistry(manifest.mongo, secrets)
        self.redis = RedisRegistry(manifest.redis, secrets)
        self.http = HttpClientRegistry()
        self._closers: list[Callable[[], None]] = []
        self._lock = threading.Lock()

    def validate_required(self, required_resources: tuple[str, ...]) -> None:
        for resource in required_resources:
            kind, separator, alias = resource.partition(":")
            if not separator or not alias:
                raise ConfigurationError(
                    "RUNTIME.INVALID_RESOURCE_DECLARATION",
                    f"Invalid required resource declaration: {resource}",
                )
            exists = {
                "mysql.database": alias in self.manifest.mysql.databases,
                "mysql.table": alias in self.manifest.mysql.tables,
                "mongo.database": alias in self.manifest.mongo.databases,
                "mongo.collection": alias in self.manifest.mongo.collections,
                "redis.connection": alias in self.manifest.redis.connections,
            }.get(kind)
            if exists is None:
                raise ConfigurationError(
                    "RUNTIME.UNKNOWN_RESOURCE_KIND",
                    f"Unknown resource kind: {kind}",
                    details={"resource": resource},
                )
            if not exists:
                raise ConfigurationError(
                    "RUNTIME.REQUIRED_RESOURCE_MISSING",
                    f"Required resource is missing: {resource}",
                    details={"resource": resource},
                )

    def register_closer(self, closer: Callable[[], None]) -> None:
        with self._lock:
            self._closers.append(closer)

    def close(self) -> list[BaseException]:
        errors: list[BaseException] = []
        with self._lock:
            closers = list(reversed(self._closers))
            self._closers.clear()
        for closer in closers:
            try:
                closer()
            except BaseException as exc:
                errors.append(exc)
        for resource in (self.http, self.redis, self.mongo, self.mysql):
            try:
                resource.close()
            except BaseException as exc:
                errors.append(exc)
        return errors


__all__ = ["ResourceManager", "SecretStore"]
