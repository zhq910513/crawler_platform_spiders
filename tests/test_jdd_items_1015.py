from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_jdd_items_task_is_discovered_with_required_platform_config() -> None:
    from crawler_foundation.tasks.registry import load_tasks

    tasks = load_tasks(ROOT / "sch.py")
    by_key = {task["definitionKey"]: task for task in tasks}
    task = by_key["jdd_items_sync"]
    assert task["entryModule"] == "spiders.jdd.items"
    assert task["entryFunction"] == "run"
    assert task["platformCode"] == "jdd"
    assert task["defaultParams"] == {
        "pageSize": 500,
        "pageNum": 1,
        "dryRun": False,
        "verifyTls": False,
        "keyword": "",
        "cities": "",
        "categoryId": "",
    }
    assert task["requiredConfigs"] == [
        {
            "slot": "mongo_jdd",
            "type": "MONGO",
            "description": "京多多商品结果库 MongoDB，由 crawler_platform 公司资源配置绑定并在运行时下发。",
            "required": True,
        }
    ]
    assert task["outputTables"] == [
        {
            "slot": "items",
            "defaultName": "jdd.items",
            "writeMethod": "upsert",
            "description": "京多多现货商品采集结果，唯一键 item_id。",
        }
    ]


def test_jdd_transform_items_preserves_item_id_and_spider_time() -> None:
    from spiders.jdd.items import transform_items

    rows = transform_items({"message": "success", "data": {"items": [{"id": 1001, "name": "铜"}, {"name": "missing"}, "bad"]}}, spider_time="2026-08-25 10:00:00")
    assert rows == [{"name": "铜", "item_id": 1001, "spider_time": "2026-08-25 10:00:00"}]


def test_jdd_mongo_config_comes_from_platform_runtime_config() -> None:
    from spiders.jdd.base import mongo_collection_from_config, mongo_database_from_config, mongo_uri_from_config

    config = {"uri": "mongodb://u:p@127.0.0.1:27017/jdd", "database": "jdd", "collection": "items"}
    assert mongo_uri_from_config(config) == "mongodb://u:p@127.0.0.1:27017/jdd"
    assert mongo_database_from_config(config) == "jdd"
    assert mongo_collection_from_config(config) == "items"
    assert mongo_uri_from_config({"host": "127.0.0.1", "port": 27017, "username": "read user", "password": "p@ss", "database": "jdd"}) == "mongodb://read+user:p%40ss@127.0.0.1:27017/jdd"


def test_jdd_mongo_config_rejects_unresolved_binding_ref() -> None:
    from crawler_foundation.core.exceptions import ConfigurationError
    from spiders.jdd.base import mongo_uri_from_config

    with pytest.raises(ConfigurationError, match="平台必须在运行时下发已解析 MongoDB 配置"):
        mongo_uri_from_config("config:jdd_result_mongo")


def test_jdd_dry_run_runtime_uses_mocked_http_without_mongo(monkeypatch, tmp_path: Path) -> None:
    import spiders.jdd.items as task

    monkeypatch.setattr(task, "fetch_items_page", lambda *args, **kwargs: {"message": "success", "data": {"items": [{"id": "A1", "title": "demo"}]}})
    monkeypatch.setenv("CRAWLER_RUN_ID", "pytest-jdd-dry-run")
    monkeypatch.setenv("CRAWLER_TASK_CODE", "jdd_items_sync")
    monkeypatch.setenv("CRAWLER_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("CRAWLER_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("CRAWLER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CRAWLER_PROFILE_DIR", str(tmp_path / "profiles"))
    result = task.run(dryRun=True, pageSize=10)
    assert result["status"] == "success"
    assert result["metrics"]["fetched"] == 1
    assert result["metrics"]["upserted"] == 0


def test_jdd_runtime_cli_dry_run_with_resolved_platform_config(tmp_path: Path) -> None:
    env = {
        "CRAWLER_RUN_ID": "pytest-jdd-cli",
        "CRAWLER_TASK_CODE": "jdd_items_sync",
        "CRAWLER_LOG_DIR": str(tmp_path / "logs"),
        "CRAWLER_WORK_DIR": str(tmp_path / "work"),
        "CRAWLER_CACHE_DIR": str(tmp_path / "cache"),
        "CRAWLER_PROFILE_DIR": str(tmp_path / "profiles"),
        "CRAWLER_CONFIG_JSON": json.dumps({"configs": {"mongo_jdd": {"uri": "mongodb://user:pass@127.0.0.1:27017/jdd", "database": "jdd", "collection": "items"}}}),
    }
    code = """
import spiders.jdd.items as t

t.fetch_items_page = lambda *a, **k: {'message': 'success', 'data': {'items': [{'id': 1, 'name': 'demo'}]}}
from crawler_runtime.__main__ import main
raise SystemExit(main(['--entrypoint','spiders.jdd.items:run','--kwargs-json','{\\"dryRun\\":true,\\"pageSize\\":10}']))
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env={**env, **{"PYTHONPATH": str(ROOT)}}, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    assert '"status": "success"' in result.stdout
    assert '"fetched": 1' in result.stdout


def test_jdd_write_path_uses_jdd_base_platform_config(monkeypatch) -> None:
    import spiders.jdd.items as task

    class FakeSink:
        def __init__(self, context):
            self.context = context
            self.closed = False

        def upsert_items(self, rows):
            assert rows == [{"item_id": "A1", "title": "demo", "spider_time": "now"}]
            return 1

        def close(self):
            self.closed = True

    monkeypatch.setattr(task, "JddBase", FakeSink)
    monkeypatch.setattr(task, "fetch_items_page", lambda *args, **kwargs: {"message": "success", "data": {"items": [{"id": "A1", "title": "demo"}]}})
    monkeypatch.setattr(task.time, "strftime", lambda *args, **kwargs: "now")

    class Logger:
        def info(self, *args, **kwargs):
            return None

    class Context:
        logger = Logger()

    result = task.run.__wrapped__(Context(), dryRun=False, pageSize=10)
    assert result.status == "success"
    assert result.metrics["upserted"] == 1
