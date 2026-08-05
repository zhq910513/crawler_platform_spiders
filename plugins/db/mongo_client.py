from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MongoConfig:
    uri: str
    connect_timeout_ms: int = 8000
    server_selection_timeout_ms: int = 8000
    max_pool_size: int = 20


class MongoClientWrapper:
    def __init__(self, config: MongoConfig) -> None:
        from pymongo import MongoClient

        self.client = MongoClient(config.uri, connectTimeoutMS=config.connect_timeout_ms, serverSelectionTimeoutMS=config.server_selection_timeout_ms, maxPoolSize=config.max_pool_size)

    def close(self) -> None:
        self.client.close()
