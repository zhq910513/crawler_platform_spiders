from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(slots=True)
class EmailConfig:
    host: str
    port: int
    username: str
    password: str
    sender: str
    use_ssl: bool = True


def send_email(config: EmailConfig, recipients: list[str], subject: str, content: str) -> None:
    if not recipients:
        return
    msg = EmailMessage()
    msg["From"] = config.sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(content)
    client_cls = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
    with client_cls(config.host, config.port, timeout=20) as server:
        server.login(config.username, config.password)
        server.send_message(msg)
