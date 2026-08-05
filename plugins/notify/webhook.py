from __future__ import annotations

from plugins.http.session import create_session


def send_json_webhook(url: str, payload: dict, *, timeout_seconds: float = 15.0) -> None:
    session = create_session(timeout_seconds=timeout_seconds, retries=1)
    response = session.post(url, json=payload)
    response.raise_for_status()
