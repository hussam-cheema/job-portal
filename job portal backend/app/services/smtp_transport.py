from __future__ import annotations

import hashlib
import json
import smtplib
import socket
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
from email.utils import getaddresses, parseaddr
from typing import Callable

import httpx

from app.config import env


StageReporter = Callable[[str, str], None]


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    username: str | None
    password: str | None
    from_email: str
    timeout: int
    use_ssl: bool
    starttls: bool
    authenticate: bool


@dataclass(frozen=True)
class SMTPDeliveryReceipt:
    message_id: str
    recipient_count: int
    response_code: int
    response: str


def email_delivery_status() -> tuple[str, bool, str]:
    """Return a secret-free delivery readiness summary for the admin UI."""
    provider = (env("EMAIL_DELIVERY_PROVIDER", "auto") or "auto").lower()
    if provider == "resend" or (provider == "auto" and env("RESEND_API_KEY")):
        ready = bool(env("RESEND_API_KEY") and env("EMAIL_FROM_EMAIL"))
        message = (
            "Resend HTTPS delivery is configured."
            if ready
            else "Set RESEND_API_KEY and EMAIL_FROM_EMAIL on backend-api and newsletter-retry."
        )
        return "resend", ready, message
    if env("RAILWAY_ENVIRONMENT") or env("RAILWAY_SERVICE_ID"):
        return (
            "unconfigured",
            False,
            "Railway Hobby blocks SMTP. Configure Resend HTTPS on backend-api and newsletter-retry.",
        )
    ready = bool(env("SMTP_HOST") and (env("SMTP_FROM_EMAIL") or env("SMTP_USERNAME")))
    return (
        "smtp",
        ready,
        "SMTP delivery is configured." if ready else "SMTP delivery is not configured.",
    )


def _message_content(message: EmailMessage) -> tuple[str, str | None]:
    plain = ""
    rich: str | None = None
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and not plain:
                plain = str(part.get_content())
            elif content_type == "text/html" and rich is None:
                rich = str(part.get_content())
    else:
        plain = str(message.get_content())
    return plain, rich


def deliver_resend_message(
    message: EmailMessage,
    *,
    reporter: StageReporter | None = None,
) -> SMTPDeliveryReceipt:
    """Deliver through Resend's HTTPS API (works on Railway Hobby)."""
    api_key = env("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY must be configured for HTTPS email delivery")
    sender, recipients = _message_addresses(message)
    plain, rich = _message_content(message)
    payload: dict[str, object] = {
        "from": str(message.get("From") or sender),
        "to": recipients,
        "subject": str(message.get("Subject") or ""),
        "text": plain,
    }
    if rich:
        payload["html"] = rich
    reply_to = parseaddr(message.get("Reply-To", ""))[1]
    if reply_to:
        payload["reply_to"] = reply_to
    if reporter:
        reporter("configuration", f"provider=resend; sender={masked_address(sender)}; recipients={len(recipients)}")
    endpoint = env("RESEND_API_URL", "https://api.resend.com/emails") or "https://api.resend.com/emails"
    with httpx.Client(timeout=float(env("EMAIL_HTTP_TIMEOUT_SECONDS", "20") or "20")) as client:
        response = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            content=json.dumps(payload),
        )
        response.raise_for_status()
        data = response.json()
    message_id = str(data.get("id") or message.get("Message-ID", ""))
    if reporter:
        reporter("accepted", f"provider accepted message id={message_id}")
    return SMTPDeliveryReceipt(
        message_id=message_id,
        recipient_count=len(recipients),
        response_code=response.status_code,
        response="accepted by Resend HTTPS API",
    )


def deliver_email_message(
    message: EmailMessage,
    *,
    reporter: StageReporter | None = None,
) -> SMTPDeliveryReceipt:
    provider = (env("EMAIL_DELIVERY_PROVIDER", "auto") or "auto").lower()
    if provider == "resend" or (provider == "auto" and env("RESEND_API_KEY")):
        return deliver_resend_message(message, reporter=reporter)
    if provider not in {"auto", "smtp"}:
        raise RuntimeError("EMAIL_DELIVERY_PROVIDER must be auto, smtp, or resend")
    # Railway disables outbound SMTP on Free, Trial, and Hobby plans. Detect a
    # Railway runtime before opening a socket so admin resend fails immediately
    # with an actionable message instead of waiting through repeated OSErrors.
    if env("RAILWAY_ENVIRONMENT") or env("RAILWAY_SERVICE_ID"):
        raise RuntimeError(
            "Railway Hobby blocks SMTP delivery. Configure EMAIL_DELIVERY_PROVIDER=resend, "
            "RESEND_API_KEY, and EMAIL_FROM_EMAIL on both backend-api and newsletter-retry."
        )
    return deliver_smtp_message(message, reporter=reporter)


def _bool_env(name: str, default: bool) -> bool:
    fallback = "true" if default else "false"
    return (env(name, fallback) or fallback).lower() in {"1", "true", "yes"}


def load_smtp_settings() -> SMTPSettings:
    host = env("SMTP_HOST")
    username = env("SMTP_USERNAME")
    password = env("SMTP_PASSWORD")
    from_email = env("SMTP_FROM_EMAIL") or username
    if not host:
        raise RuntimeError("SMTP_HOST must be configured")
    if not from_email:
        raise RuntimeError("SMTP_FROM_EMAIL or SMTP_USERNAME must be configured")
    port = int(env("SMTP_PORT", "587") or "587")
    use_ssl = _bool_env("SMTP_USE_SSL", port == 465)
    authenticate = _bool_env("SMTP_AUTH", bool(username))
    if host.lower() == "smtp.gmail.com" and password:
        # Google renders app passwords in four groups. Whitespace copied from
        # that display is not part of the credential.
        password = "".join(password.split())
    if authenticate and (not username or not password):
        raise RuntimeError(
            "SMTP_USERNAME and SMTP_PASSWORD must be configured when SMTP_AUTH is enabled"
        )
    return SMTPSettings(
        host=host,
        port=port,
        username=username,
        password=password,
        from_email=from_email,
        timeout=int(env("SMTP_TIMEOUT_SECONDS", "15") or "15"),
        use_ssl=use_ssl,
        starttls=_bool_env("SMTP_STARTTLS", not use_ssl),
        authenticate=authenticate,
    )


def masked_address(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator:
        return "***"
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


def address_fingerprint(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:12]


def resolve_smtp_host(settings: SMTPSettings) -> int:
    """Resolve the configured server and return the number of socket addresses."""
    return len(socket.getaddrinfo(settings.host, settings.port, type=socket.SOCK_STREAM))


def _message_addresses(message: EmailMessage) -> tuple[str, list[str]]:
    sender = parseaddr(message.get("From", ""))[1]
    if not sender:
        raise RuntimeError("The email message does not contain a valid From address")
    values = message.get_all("To", []) + message.get_all("Cc", []) + message.get_all(
        "Bcc", []
    )
    recipients = [address for _name, address in getaddresses(values) if address]
    if not recipients:
        raise RuntimeError("The email message does not contain a recipient")
    return sender, recipients


def deliver_smtp_message(
    message: EmailMessage,
    *,
    reporter: StageReporter | None = None,
) -> SMTPDeliveryReceipt:
    """Deliver a message and expose the final SMTP acceptance response.

    A successful return means the receiving SMTP server accepted responsibility
    for the message. SMTP cannot prove that a provider placed it in Inbox rather
    than Spam, Promotions, a filtered folder, or a delayed delivery queue.
    """

    settings = load_smtp_settings()
    sender, recipients = _message_addresses(message)

    def report(stage: str, detail: str) -> None:
        if reporter:
            reporter(stage, detail)

    report(
        "configuration",
        f"server={settings.host}:{settings.port}; auth={settings.authenticate}; "
        f"password={'present' if settings.password else 'absent'}; "
        f"sender={masked_address(sender)}; recipients={len(recipients)}",
    )
    addresses = resolve_smtp_host(settings)
    report("dns", f"resolved {addresses} TCP address(es)")

    context = ssl.create_default_context()
    smtp_factory = smtplib.SMTP_SSL if settings.use_ssl else smtplib.SMTP
    kwargs = {"context": context} if settings.use_ssl else {}
    with smtp_factory(
        settings.host,
        settings.port,
        timeout=settings.timeout,
        **kwargs,
    ) as smtp:
        report("connect", "TCP connection established")
        code, _response = smtp.ehlo()
        if code != 250:
            raise smtplib.SMTPHeloError(code, _response)
        report("ehlo", f"server replied {code}")

        if not settings.use_ssl and settings.starttls:
            code, response = smtp.starttls(context=context)
            if code != 220:
                raise smtplib.SMTPResponseException(code, response)
            report("tls", f"STARTTLS accepted with {code}")
            code, response = smtp.ehlo()
            if code != 250:
                raise smtplib.SMTPHeloError(code, response)
        elif settings.use_ssl:
            report("tls", "implicit TLS connection established")
        else:
            report("tls", "disabled by configuration")

        if settings.authenticate:
            code, response = smtp.login(settings.username or "", settings.password or "")
            if code not in {235, 503}:
                raise smtplib.SMTPAuthenticationError(code, response)
            report("authentication", f"credentials accepted with {code}")
        else:
            report("authentication", "disabled by configuration")

        code, response = smtp.mail(sender)
        if code != 250:
            raise smtplib.SMTPSenderRefused(code, response, sender)
        report("mail_from", f"envelope sender accepted with {code}")

        refused: dict[str, tuple[int, bytes]] = {}
        for recipient in recipients:
            code, response = smtp.rcpt(recipient)
            if code not in {250, 251}:
                refused[recipient] = (code, response)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
        report("recipients", f"all {len(recipients)} recipient(s) accepted")

        # Bcc must remain an envelope-only address.
        if "Bcc" in message:
            del message["Bcc"]
        code, response = smtp.data(message.as_bytes(policy=SMTP_POLICY))
        if code != 250:
            raise smtplib.SMTPDataError(code, response)
        decoded = response.decode("utf-8", errors="replace")
        report("data", f"message accepted with {code}: {decoded}")

    return SMTPDeliveryReceipt(
        message_id=str(message.get("Message-ID", "")),
        recipient_count=len(recipients),
        response_code=code,
        response=decoded,
    )
