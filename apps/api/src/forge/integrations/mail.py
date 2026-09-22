import os
import smtplib
import ssl
from email.message import EmailMessage
from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from forge.config import Settings
from forge.domain.identity import DomainError


class MailDelivery:
    """Explicit local sink or authenticated TLS SMTP; no tokens in application logs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, email: str, purpose: str, token: str) -> None:
        route, subject = {
            "verify": ("verify-email", "Verify your Forge email"),
            "reset": ("reset-password", "Reset your Forge password"),
            "invite": ("invite", "You have been invited to Forge"),
        }[purpose]
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = email
        message["Subject"] = subject
        message.set_content(
            f"{subject}\n\n"
            f"{self.settings.public_origin}/{route}#token={token}\n\n"
            "This link is single-use and expires. If you did not request it, ignore this message.\n"
        )
        try:
            await run_in_threadpool(self._deliver, message)
        except (OSError, smtplib.SMTPException) as exc:
            raise DomainError(
                503, "mail_unavailable", "Email delivery is temporarily unavailable."
            ) from exc

    def _deliver(self, message: EmailMessage) -> None:
        if self.settings.mail_backend == "file":
            directory = self.settings.mail_directory
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            target = directory / f"{uuid4()}.eml"
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(message.as_bytes())
            return
        assert (
            self.settings.smtp_host and self.settings.smtp_username and self.settings.smtp_password
        )
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(self.settings.smtp_username, self.settings.smtp_password.get_secret_value())
            smtp.send_message(message)
