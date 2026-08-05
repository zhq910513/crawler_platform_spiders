from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import os
import sys
import traceback
from typing import Any, Callable

_FAILED_STATUSES = {"failed", "error"}
_SUCCESS_STATUSES = {"success", "partial_success", "skipped"}
_EXIT_BY_ERROR_CODE_PREFIX = {
    "SPIDER.PARAMETER": 10,
    "SPIDER.CONFIG": 20,
    "SPIDER.LOGIN": 30,
    "SPIDER.CAPTCHA": 40,
    "SPIDER.NETWORK": 50,
    "SPIDER.DATABASE": 60,
    "SPIDER.NO_DATA": 70,
    "SPIDER.PARSE": 80,
}


def resolve_callable(entrypoint: str) -> Callable[..., Any]:
    value = entrypoint.strip()
    if ":" in value:
        module_name, attr_path = value.split(":", 1)
    else:
        module_name, _, attr_path = value.rpartition(".")
    if not module_name or not attr_path:
        raise ValueError("entrypoint 必须为 package.module:function 或 package.module.function")
    target: Any = importlib.import_module(module_name)
    for attr in attr_path.split("."):
        target = getattr(target, attr)
    if not callable(target):
        raise TypeError(f"目标对象不可调用：{entrypoint}")
    return target


def parse_json(value: str, expected_type: type) -> Any:
    result = json.loads(value)
    if not isinstance(result, expected_type):
        raise TypeError(f"参数必须解析为 {expected_type.__name__}")
    return result


def emit_result(result: Any) -> None:
    if result is None:
        return
    try:
        print(json.dumps({"runtime_result": result}, ensure_ascii=False, default=str), flush=True)
    except Exception:
        print(f"runtime_result={result!r}", flush=True)


def _exit_code_from_result(result: Any) -> int:
    if not isinstance(result, dict):
        return 0
    status = str(result.get("status") or "").lower()
    if status in _SUCCESS_STATUSES or not status:
        return 0
    if status not in _FAILED_STATUSES:
        return 0
    for container in (result, result.get("error") if isinstance(result.get("error"), dict) else {}):
        raw = container.get("exitCode") or container.get("exit_code")
        if raw is not None:
            try:
                value = int(raw)
                return value if value > 0 else 1
            except Exception:
                pass
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    code = str(error.get("code") or result.get("code") or "")
    for prefix, exit_code in _EXIT_BY_ERROR_CODE_PREFIX.items():
        if code.startswith(prefix):
            return exit_code
    return 90


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crawler Runtime Method Runner")
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--args-json", default="[]")
    parser.add_argument("--kwargs-json", default="{}")
    args = parser.parse_args(argv)
    try:
        positional = parse_json(args.args_json, list)
        keyword = parse_json(args.kwargs_json, dict)
        env_keyword_raw = os.getenv("CRAWLER_TASK_PARAMS_JSON")
        if env_keyword_raw:
            env_keyword = parse_json(env_keyword_raw, dict)
            keyword = {**env_keyword, **keyword}
        target = resolve_callable(args.entrypoint)
        result = target(*positional, **keyword)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        emit_result(result)
        return _exit_code_from_result(result)
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
