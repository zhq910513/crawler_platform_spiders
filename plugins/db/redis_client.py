from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RedisConfig:
    host: str
    port: int = 6379
    db: int = 0
    password: str | None = None
    username: str | None = None
    key_prefix: str = ""
    socket_timeout: float = 30.0


class RedisClient:
    def __init__(self, config: RedisConfig) -> None:
        import redis

        self.config = config
        self.client = redis.Redis(host=config.host, port=config.port, db=config.db, username=config.username, password=config.password, socket_timeout=config.socket_timeout, decode_responses=True)

    def key(self, name: str) -> str:
        return f"{self.config.key_prefix}{name}"

    def close(self) -> None:
        self.client.close()
        self.client.connection_pool.disconnect()
