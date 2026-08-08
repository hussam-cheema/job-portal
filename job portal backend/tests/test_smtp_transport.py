from __future__ import annotations

import smtplib
import json
from email.message import EmailMessage

import pytest


def _message() -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "SMTP transport test"
    message["From"] = "Pakistan Jobs Market <sender@example.test>"
    message["To"] = "reader@example.test"
    message["Message-ID"] = "<transport-test@example.test>"
    message.set_content("Test body")
    return message


def _smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "test-password")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "sender@example.test")
    monkeypatch.setenv("SMTP_AUTH", "true")
    monkeypatch.setenv("SMTP_STARTTLS", "true")
    monkeypatch.setenv("SMTP_USE_SSL", "false")


def test_staged_smtp_transport_reports_final_acceptance(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import smtp_transport

    _smtp_env(monkeypatch)
    calls: list[tuple] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            calls.append(("ehlo",))
            return 250, b"hello"

        def starttls(self, *, context):
            calls.append(("starttls", bool(context)))
            return 220, b"ready"

        def login(self, username: str, password: str):
            calls.append(("login", username, password))
            return 235, b"accepted"

        def mail(self, sender: str):
            calls.append(("mail", sender))
            return 250, b"ok"

        def rcpt(self, recipient: str):
            calls.append(("rcpt", recipient))
            return 250, b"ok"

        def data(self, payload: bytes):
            calls.append(("data", b"Test body" in payload))
            return 250, b"2.0.0 queued as test-123"

    monkeypatch.setattr(smtp_transport.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(
        smtp_transport.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(object(),)],
    )
    stages: list[str] = []
    receipt = smtp_transport.deliver_smtp_message(
        _message(), reporter=lambda stage, _detail: stages.append(stage)
    )

    assert receipt.response_code == 250
    assert "queued as test-123" in receipt.response
    assert receipt.recipient_count == 1
    assert stages == [
        "configuration",
        "dns",
        "connect",
        "ehlo",
        "tls",
        "authentication",
        "mail_from",
        "recipients",
        "data",
    ]
    assert ("login", "sender@example.test", "test-password") in calls
    assert ("rcpt", "reader@example.test") in calls
    assert ("data", True) in calls


def test_staged_smtp_transport_identifies_authentication_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import smtp_transport

    _smtp_env(monkeypatch)

    class RejectingSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            return 250, b"hello"

        def starttls(self, *, context):
            return 220, b"ready"

        def login(self, _username: str, _password: str):
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(smtp_transport.smtplib, "SMTP", RejectingSMTP)
    monkeypatch.setattr(
        smtp_transport.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(object(),)],
    )
    stages: list[str] = []
    with pytest.raises(smtplib.SMTPAuthenticationError) as caught:
        smtp_transport.deliver_smtp_message(
            _message(), reporter=lambda stage, _detail: stages.append(stage)
        )

    assert caught.value.smtp_code == 535
    assert stages[-1] == "tls"


def test_gmail_app_password_is_normalized(monkeypatch: pytest.MonkeyPatch):
    from app.services.smtp_transport import load_smtp_settings

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "sender@gmail.com")

    assert load_smtp_settings().password == "abcdefghijklmnop"


def test_resend_https_delivery_avoids_blocked_smtp_ports(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import smtp_transport

    monkeypatch.setenv("EMAIL_DELIVERY_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "resend-message-id"}

    class FakeClient:
        def __init__(self, *, timeout: float):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, endpoint: str, *, headers: dict[str, str], content: str):
            captured["endpoint"] = endpoint
            captured["headers"] = headers
            captured["payload"] = json.loads(content)
            return FakeResponse()

    monkeypatch.setattr(smtp_transport.httpx, "Client", FakeClient)
    stages: list[str] = []

    receipt = smtp_transport.deliver_email_message(
        _message(), reporter=lambda stage, _detail: stages.append(stage)
    )

    assert receipt.message_id == "resend-message-id"
    assert receipt.recipient_count == 1
    assert captured["endpoint"] == "https://api.resend.com/emails"
    assert captured["payload"] == {
        "from": "Pakistan Jobs Market <sender@example.test>",
        "to": ["reader@example.test"],
        "subject": "SMTP transport test",
        "text": "Test body\n",
    }
    assert stages == ["configuration", "accepted"]
