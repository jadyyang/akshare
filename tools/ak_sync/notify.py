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

    if config.security == "ssl":
        smtp_client = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
    else:
        smtp_client = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)

    with smtp_client as smtp:
        if config.security == "starttls":
            smtp.starttls()
        smtp.login(config.username, config.password)
        smtp.send_message(message)
