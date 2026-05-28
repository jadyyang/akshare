from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import MailConfig


def send_mail(config: MailConfig, subject: str, body: str) -> None:
    if not config.enabled:
        return
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.from_addr
    message["To"] = ", ".join(config.to_addrs)
    message.set_content(body)

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        if config.use_tls:
            smtp.starttls()
        smtp.login(config.username, config.password)
        smtp.send_message(message)

