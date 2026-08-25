from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from crawler_foundation.core.exceptions import ConfigurationError, StorageError

MONGO_SLOT = "mongo_jdd"
DEFAULT_DATABASE = "jdd"
DEFAULT_COLLECTION = "items"


class JddBase:
    """京多多平台共享能力。

    只从 crawler_platform 下发的运行时配置读取 MongoDB 信息，不从任务参数、环境变量
    或业务代码硬编码生产数据库连接。配置槽位由 TASK_DEFINITION.requiredConfigs 声明。
    """

    def __init__(self, context: Any, *, mongo_slot: str = MONGO_SLOT) -> None:
        self.context = context
        self.mongo_slot = mongo_slot
        self._mongo_client: Any | None = None

    def load_mongo_config(self) -> dict[str, Any] | str:
        try:
            config = self.context.config.mongo(self.mongo_slot)
        except KeyError as exc:
            raise ConfigurationError(f"平台未下发必需配置槽位：{self.mongo_slot}") from exc
        if config in (None, "", {}):
            raise ConfigurationError(f"平台下发的配置槽位为空：{self.mongo_slot}")
        return config

    def open_items_collection(self):
        try:
            from pymongo import MongoClient
        except Exception as exc:
            raise StorageError("pymongo 未安装，无法写入 MongoDB") from exc

        config = self.load_mongo_config()
        uri = mongo_uri_from_config(config, slot=self.mongo_slot)
        database = mongo_database_from_config(config)
        collection = mongo_collection_from_config(config)
        self._mongo_client = MongoClient(uri, connectTimeoutMS=8000, serverSelectionTimeoutMS=8000, maxPoolSize=20)
        return self._mongo_client[database][collection]

    def close(self) -> None:
        if self._mongo_client is not None:
            self._mongo_client.close()
            self._mongo_client = None

    def upsert_items(self, rows: list[dict[str, Any]]) -> int:
        collection = self.open_items_collection()
        written = 0
        for row in rows:
            item_id = row.get("item_id")
            if item_id in (None, ""):
                continue
            collection.update_one({"item_id": item_id}, {"$set": row}, upsert=True)
            written += 1
        return written


def mongo_uri_from_config(config: dict[str, Any] | str, *, slot: str = MONGO_SLOT) -> str:
    if isinstance(config, str):
        value = config.strip()
        if value.startswith("mongodb://") or value.startswith("mongodb+srv://"):
            return value
        raise ConfigurationError(f"{slot} 仍是绑定引用或非法 URI，平台必须在运行时下发已解析 MongoDB 配置")
    if not isinstance(config, dict):
        raise ConfigurationError(f"{slot} 配置必须是 MongoDB URI 字符串或对象")

    for key in ("uri", "connectionString", "connection_string", "url", "dsn"):
        value = str(config.get(key) or "").strip()
        if value:
            if value.startswith("mongodb://") or value.startswith("mongodb+srv://"):
                return value
            raise ConfigurationError(f"{slot}.{key} 不是合法 MongoDB URI")

    host = str(config.get("host") or "").strip()
    if not host:
        raise ConfigurationError(f"{slot} 配置缺少 uri/host")
    port = int(config.get("port") or 27017)
    username = str(config.get("username") or config.get("user") or "").strip()
    password = str(config.get("password") or "").strip()
    auth_database = str(config.get("authDatabase") or config.get("authSource") or config.get("database") or DEFAULT_DATABASE).strip()
    auth_part = f"{quote_plus(username)}:{quote_plus(password)}@" if username else ""
    return f"mongodb://{auth_part}{host}:{port}/{auth_database}"


def mongo_database_from_config(config: dict[str, Any] | str) -> str:
    if isinstance(config, dict):
        value = str(config.get("database") or config.get("db") or DEFAULT_DATABASE).strip()
        return value or DEFAULT_DATABASE
    return DEFAULT_DATABASE


def mongo_collection_from_config(config: dict[str, Any] | str) -> str:
    if isinstance(config, dict):
        value = str(config.get("collection") or config.get("table") or DEFAULT_COLLECTION).strip()
        return value or DEFAULT_COLLECTION
    return DEFAULT_COLLECTION
