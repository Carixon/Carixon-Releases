from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional

from ..utils.logger import get_logger


@dataclass(slots=True)
class EmailConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True
    sender: Optional[str] = None


class EmailService:
    def __init__(self, config: EmailConfig | None = None) -> None:
        self._logger = get_logger("EmailService")
        self._config = config

    def configure(self, config: EmailConfig) -> None:
        self._config = config

    def send(self, recipients: Iterable[str], subject: str, body: str, attachments: Iterable[Path] = ()) -> None:
        if not self._config:
            raise ValueError("Email service not configured")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._config.sender or self._config.username
        message["To"] = ", ".join(recipients)
        message.set_content(body, subtype="html")

        for attachment in attachments:
            data = attachment.read_bytes()
            message.add_attachment(
                data,
                maintype="application",
                subtype="octet-stream",
                filename=attachment.name,
            )

        if self._config.use_tls:
            server = smtplib.SMTP(self._config.host, self._config.port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(self._config.host, self._config.port)
        try:
            server.login(self._config.username, self._config.password)
            server.send_message(message)
            self._logger.info("Sent email to %s", recipients)
        finally:
            server.quit()


email_service = EmailService()
