"""Transactional email providers behind one interface.

* SmtpProvider    — any SMTP server (Gmail app password, Mailtrap, SES SMTP, …)
* ResendProvider  — https://resend.com HTTP API
* PreviewProvider — default when nothing is configured: stores the email for in-app preview, sends nothing

Credentials are read from the environment only and never leave the backend.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from typing import Protocol

import httpx

from app.core.config import Settings


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    html: str
    text: str


class EmailDeliveryError(Exception):
    """Raised by providers; the message is safe to log (no credentials)."""


class EmailProvider(Protocol):
    name: str

    async def send(self, email: OutgoingEmail) -> None: ...


class PreviewProvider:
    name = "preview"

    async def send(self, email: OutgoingEmail) -> None:  # nothing leaves the server
        return None


class SmtpProvider:
    name = "smtp"

    def __init__(self, settings: Settings) -> None:
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.use_ssl = settings.smtp_use_ssl
        self.use_tls = settings.smtp_use_tls
        self.sender = settings.sender
        self.timeout = 20

    def _send_sync(self, email: OutgoingEmail) -> None:
        msg = MimeMessage()
        msg["From"] = self.sender
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.text)
        msg.add_alternative(email.html, subtype="html")
        try:
            if self.use_ssl:
                server: smtplib.SMTP = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout,
                                                        context=ssl.create_default_context())
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            with server:
                if self.use_tls and not self.use_ssl:
                    server.starttls(context=ssl.create_default_context())
                if self.user:
                    server.login(self.user, self.password)
                server.send_message(msg)
        except smtplib.SMTPAuthenticationError:
            raise EmailDeliveryError("SMTP authentication failed") from None
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailDeliveryError(f"SMTP error: {type(exc).__name__}") from None

    async def send(self, email: OutgoingEmail) -> None:
        await asyncio.to_thread(self._send_sync, email)


class ResendProvider:
    name = "resend"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.key = settings.resend_api_key
        self.sender = settings.email_from
        self.transport = transport

    async def send(self, email: OutgoingEmail) -> None:
        try:
            async with httpx.AsyncClient(timeout=20, transport=self.transport) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self.key}"},
                    json={"from": self.sender, "to": [email.to], "subject": email.subject, "html": email.html,
                          "text": email.text})
        except httpx.HTTPError as exc:
            raise EmailDeliveryError(f"Resend request failed: {type(exc).__name__}") from None
        if response.status_code >= 400:
            raise EmailDeliveryError(f"Resend rejected the email (HTTP {response.status_code})")


def get_email_provider(settings: Settings) -> EmailProvider:
    choice = settings.email_provider.lower()
    if choice == "smtp" or (choice == "auto" and settings.smtp_host):
        return SmtpProvider(settings)
    if choice == "resend" or (choice == "auto" and settings.resend_api_key):
        return ResendProvider(settings)
    return PreviewProvider()
