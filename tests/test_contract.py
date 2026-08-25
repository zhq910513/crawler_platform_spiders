from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _base_env(tmp_path: Path, *, task_code: str = "system_health") -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "CRAWLER_RUN_ID": "pytest-run",
            "CRAWLER_LOG_DIR": str(tmp_path / "logs"),
            "CRAWLER_WORK_DIR": str(tmp_path / "work"),
            "CRAWLER_CACHE_DIR": str(tmp_path / "cache"),
            "CRAWLER_PROFILE_DIR": str(tmp_path / "profiles"),
            "CRAWLER_TASK_CODE": task_code,
        }
    )
    return env


def test_project_does_not_have_duplicate_nested_package_name() -> None:
    assert not (ROOT / "crawler_platform_spiders" / "crawler_platform_spiders").exists()
    assert (ROOT / "crawler_foundation").is_dir()
    assert (ROOT / "crawler_platform_spiders.py").is_file()


def test_sch_tasks_are_static_and_importable() -> None:
    from crawler_foundation.tasks.registry import load_tasks

    tasks = load_tasks(ROOT / "sch.py")
    assert tasks
    keys = {item["definitionKey"] for item in tasks}
    assert "system_health" in keys
    assert "demo_async_echo" in keys
    for task in tasks:
        module = importlib.import_module(task["entryModule"])
        assert callable(getattr(module, task["entryFunction"]))


def test_manifest_matches_platform_contract() -> None:
    from crawler_foundation.tasks.registry import build_manifest, load_tasks

    manifest = build_manifest(
        tasks=load_tasks(ROOT / "sch.py"),
        project_key="crawler_platform_spiders",
        project_code="crawler_platform_spiders",
        project_name="通用爬虫项目基建",
        image_repository="crawler_platform_spiders",
        image_digest="sha256:" + "1" * 64,
        release_version="1.0.17",
    )
    assert manifest["manifestVersion"] == "1"
    assert manifest["taskDefinitions"][0]["definitionKey"]
    assert manifest["taskDefinitions"][0]["entryModule"].startswith("spiders.")


def test_crawler_runtime_can_run_health(tmp_path: Path) -> None:
    env = _base_env(tmp_path, task_code="system_health")
    result = subprocess.run(
        [sys.executable, "-m", "crawler_runtime", "--entrypoint", "spiders.system.health:run", "--kwargs-json", json.dumps({"message": "pytest ok"})],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "pytest ok" in result.stdout
    assert (tmp_path / "logs").exists()


def test_runtime_can_run_async_decorated_task(tmp_path: Path) -> None:
    env = _base_env(tmp_path, task_code="demo_async_echo")
    result = subprocess.run(
        [sys.executable, "-m", "crawler_runtime", "--entrypoint", "spiders.demo.async_echo:run", "--kwargs-json", json.dumps({"text": "async-ok"})],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "async-ok" in result.stdout


def test_local_cli_run_echo(tmp_path: Path) -> None:
    env = _base_env(tmp_path, task_code="demo_echo")
    result = subprocess.run(
        [sys.executable, "-m", "crawler_platform_spiders", "run", "--task-code", "demo_echo", "--kwargs-json", json.dumps({"text": "A", "repeat": 3})],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "AAA" in result.stdout


def test_installed_console_script_target_imports() -> None:
    from crawler_foundation.cli import main
    from crawler_platform_spiders import __version__

    assert callable(main)
    assert __version__ == "1.0.17"


def test_sch_can_be_generated_from_spider_static_definitions() -> None:
    from crawler_foundation.tasks.discovery import discover_tasks
    from scripts.sync_sch import render

    discovered = discover_tasks(ROOT)
    assert (ROOT / "sch.py").read_text(encoding="utf-8") == render(discovered)


def test_runtime_failed_task_returns_non_zero_exit_code(tmp_path: Path) -> None:
    env = _base_env(tmp_path, task_code="system_health")
    env["CRAWLER_RUN_ID"] = "pytest-failed-run"
    result = subprocess.run(
        [sys.executable, "-m", "crawler_runtime", "--entrypoint", "spiders.system.health:run", "--kwargs-json", json.dumps({"raise_login_error": True})],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 30, result.stderr + result.stdout
    assert "runtime_result" in result.stdout
    assert (tmp_path / "logs" / "pytest-failed-run.last_error.json").exists()


def test_context_merges_agent_parameter_env(tmp_path: Path) -> None:
    env = _base_env(tmp_path, task_code="demo_echo")
    env["CRAWLER_RUN_ID"] = "pytest-env-params"
    env["CRAWLER_TASK_PARAMS_JSON"] = json.dumps({"companyId": 9, "text": "from-env"})
    result = subprocess.run(
        [sys.executable, "-m", "crawler_runtime", "--entrypoint", "spiders.demo.echo:run", "--kwargs-json", json.dumps({"repeat": 2})],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "from-envfrom-env" in result.stdout


def test_create_task_script_preview_does_not_write(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/create_task.py",
            "--platform",
            "pytest_new",
            "--definition-key",
            "pytest_new_demo",
            "--task-name",
            "pytest 新任务",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "spiders/pytest_new/demo.py" in result.stdout.replace("\\", "/")
    assert not (ROOT / "spiders" / "pytest_new" / "demo.py").exists()


def test_oilchem_task_is_discovered_and_static() -> None:
    from crawler_foundation.tasks.registry import load_tasks

    tasks = load_tasks(ROOT / "sch.py")
    by_key = {task["definitionKey"]: task for task in tasks}
    assert "oilchem_login_check" in by_key
    assert by_key["oilchem_login_check"]["entryModule"] == "spiders.oilchem.login"
    assert by_key["oilchem_login_check"]["taskGroup"] == "oilchem"


def test_oilchem_cookie_token_parsing(tmp_path: Path) -> None:
    from crawler_foundation.core.context import TaskContext
    from spiders.oilchem.base import OilchemAccount, OilchemBase

    env = _base_env(tmp_path, task_code="oilchem_login_check")
    old = os.environ.copy()
    os.environ.update(env)
    try:
        context = TaskContext.from_env({})
        base = OilchemBase(context)
        assert base.extract_token_from_cookie_cache('_member_user_tonken_=abc.def;refpay=0') == 'abc.def'
        assert base.extract_token_from_cookie_cache({'cookies': {'_member_user_tonken_': 'jwt-token'}}) == 'jwt-token'
        account = OilchemAccount.from_payload({'account': {'username': 'zhq_test', 'cookieString': '_member_user_tonken_=cookie-token;refpay=0'}})
        assert account.username == 'zhq_test'
        assert base.token_from_input(account) == 'cookie-token'
    finally:
        os.environ.clear()
        os.environ.update(old)


def test_oilchem_login_task_without_token_returns_login_error(tmp_path: Path) -> None:
    env = _base_env(tmp_path, task_code="oilchem_login_check")
    env.pop("REDIS_URL", None)
    env.pop("MONGO_URI", None)
    result = subprocess.run(
        [sys.executable, "-m", "crawler_runtime", "--entrypoint", "spiders.oilchem.login:run", "--kwargs-json", json.dumps({"username": "pytest_user"})],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 30, result.stderr + result.stdout
    assert "runtime_result" in result.stdout
    assert "token 不存在" in result.stdout


def test_mysql_insert_rows_builds_safe_table_sql() -> None:
    from plugins.db.mysql import MySQLClient, MySQLConfig

    class DummyMySQL(MySQLClient):
        def __init__(self) -> None:
            super().__init__(MySQLConfig(host="localhost", port=3306, user="u", password="p", database="d"))
            self.sql = ""
            self.rows = []

        def executemany(self, sql, rows):  # type: ignore[override]
            self.sql = sql
            self.rows = list(rows)
            return len(self.rows)

    db = DummyMySQL()
    assert db.insert_rows("oilchem_table", [{"dt": "2026-08-05", "price": 1}], mode="replace") == 1
    assert db.sql == "REPLACE INTO `oilchem_table` (`dt`, `price`) VALUES (%(dt)s, %(price)s)"
    try:
        db.insert_rows("oilchem_table;drop", [{"dt": "x"}])
    except Exception as exc:
        assert "标识符" in str(exc)
    else:
        raise AssertionError("unsafe table name should fail")


def test_oilchem_password_form_matches_har_fields(tmp_path: Path) -> None:
    from crawler_foundation.core.context import TaskContext
    from crawler_foundation.core.exceptions import LoginError
    from spiders.oilchem.base import OilchemAccount, OilchemBase

    env = _base_env(tmp_path, task_code="oilchem_login_check")
    old = os.environ.copy()
    os.environ.update(env)
    try:
        context = TaskContext.from_env({})
        base = OilchemBase(context)
        account = OilchemAccount.from_payload(
            {
                "account": {
                    "username": "pytest_user",
                    "password": "plain-password",
                    "captchaValidate": "validate-token",
                }
            }
        )
        form = base.build_login_form(account)
        assert form["username"] == "pytest_user"
        assert form["password"] == "9a0ef3ecf101a8b0856f98eb6b2e2c24"
        assert form["errorPaw"] == "(9a0ef3ecf101a8b0856f98eb6b2e2c24)"
        assert form["agree"] == "on"
        assert form["NECaptchaValidate"] == "validate-token"
        assert form["vcode"] == "validate-token"
        assert form["captchaId"] == "a17cc715e78a4afc8c43cd85da9d7254"
        assert form["target"] == "https://dc.oilchem.net/page/#/index"
        md5_account = OilchemAccount.from_payload(
            {
                "account": {
                    "username": "pytest_user",
                    "password": "0AD138AE1E13592278068CCFA53074F5",
                    "captchaValidate": "validate-token",
                }
            }
        )
        assert base.build_login_form(md5_account)["password"] == "0ad138ae1e13592278068ccfa53074f5"
        try:
            base.build_login_form(OilchemAccount.from_payload({"username": "pytest_user", "password": "plain-password"}))
        except LoginError as exc:
            assert "NECaptchaValidate" in str(exc)
        else:
            raise AssertionError("password login without NECaptchaValidate should fail")
    finally:
        os.environ.clear()
        os.environ.update(old)
        try:
            base.close()
        except Exception:
            pass


def test_oilchem_password_login_extracts_cookie_token_without_network(tmp_path: Path) -> None:
    from crawler_foundation.core.context import TaskContext
    from spiders.oilchem.base import OilchemAccount, OilchemBase

    class FakeCookieJar(dict):
        def set(self, key, value, *args, **kwargs):
            self[key] = value

        def get_dict(self):
            return dict(self)

    class FakeResponse:
        status_code = 302
        text = ""
        headers = {"Location": "https://dc.oilchem.net/page/#/index", "Set-Cookie": "_member_user_tonken_=jwt-token; Domain=oilchem.net; Path=/"}
        cookies = FakeCookieJar({"_member_user_tonken_": "jwt-token", "_pass": "must-not-persist"})

        def json(self):
            return {}

    class FakeSession:
        def __init__(self):
            self.cookies = FakeCookieJar()
            self.post_data = None
            self.post_headers = None

        def get(self, *args, **kwargs):
            return FakeResponse()

        def post(self, url, headers=None, data=None, **kwargs):
            self.post_data = data
            self.post_headers = headers
            self.cookies.update(FakeResponse.cookies)
            return FakeResponse()

        def close(self):
            pass

    env = _base_env(tmp_path, task_code="oilchem_login_check")
    old = os.environ.copy()
    os.environ.update(env)
    try:
        context = TaskContext.from_env({})
        base = OilchemBase(context)
        fake_session = FakeSession()
        base.session = fake_session
        base.check_login_by_token = lambda token: "1175374"  # type: ignore[method-assign]
        account = OilchemAccount.from_payload(
            {
                "account": {
                    "username": "pytest_user",
                    "password": "plain-password",
                    "NECaptchaValidate": "validate-token",
                }
            }
        )
        result = base.password_login(account, check=True, persist=False)
        assert result["loginMode"] == "password"
        assert result["userId"] == "1175374"
        assert result["redirectLocation"] == "https://dc.oilchem.net/page/#/index"
        assert "_member_user_tonken_" in result["cookieNames"]
        assert "_pass" not in result["cookieNames"]
        assert fake_session.post_data["password"] == "9a0ef3ecf101a8b0856f98eb6b2e2c24"
        assert fake_session.post_data["NECaptchaValidate"] == "validate-token"
        assert fake_session.post_headers["Content-Type"] == "application/x-www-form-urlencoded"
    finally:
        os.environ.clear()
        os.environ.update(old)
        try:
            base.close()
        except Exception:
            pass


def test_passive_build_contract_shell_syntax() -> None:
    for script in ["scripts/build_and_register.sh", "scripts/platform_build_contract.sh"]:
        result = subprocess.run(["bash", "-n", script], cwd=str(ROOT), text=True, capture_output=True, timeout=20)
        assert result.returncode == 0, result.stderr + result.stdout


def test_context_checkpoint_and_offline_policy_fields(tmp_path: Path) -> None:
    from crawler_foundation.core.context import TaskContext
    from crawler_foundation.tasks.registry import load_tasks

    env = _base_env(tmp_path, task_code="demo_echo")
    old = os.environ.copy()
    os.environ.update(env)
    try:
        context = TaskContext.from_env({})
        context.checkpoint.save("lastPage", 3)
        assert context.checkpoint.load("lastPage") == 3
        context.checkpoint.mark_done()
        assert context.checkpoint.load("done") is True
    finally:
        os.environ.clear()
        os.environ.update(old)
    tasks = load_tasks(ROOT / "sch.py")
    for task in tasks:
        assert "allowOfflineRun" in task
        assert "offlinePolicy" in task
