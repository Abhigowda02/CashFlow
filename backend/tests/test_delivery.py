"""Tests for notification delivery module."""
from unittest.mock import MagicMock, patch
from backend.modules.delivery import (
    build_mailto_link,
    build_sms_link,
    build_whatsapp_link,
    normalize_indian_phone,
    send_email,
)


def test_normalize_indian_phone():
    assert normalize_indian_phone("9876543210") == "919876543210"
    assert normalize_indian_phone("+91 98765 43210") == "919876543210"
    assert normalize_indian_phone("09876543210") == "919876543210"
    assert normalize_indian_phone("919876543210") == "919876543210"
    assert normalize_indian_phone("") is None
    assert normalize_indian_phone(None) is None


def test_build_whatsapp_link():
    link = build_whatsapp_link("9876543210", "Hello Ramesh ji, please check invoice.")
    assert link is not None
    assert link.startswith("https://wa.me/919876543210?text=")
    assert "Hello" in link
    assert build_whatsapp_link(None, "Text") is None


def test_build_sms_link():
    link = build_sms_link("9876543210", "Reminder message")
    assert link is not None
    assert link.startswith("sms:919876543210?body=")
    assert build_sms_link(None, "Text") is None


def test_build_mailto_link():
    link = build_mailto_link("test@example.com", "Payment due", "Invoice details")
    assert link is not None
    assert link.startswith("mailto:test@example.com?subject=Payment%20due&body=")
    assert build_mailto_link(None, "Sub", "Body") is None


def test_send_email_mock_fallback(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    res = send_email("customer@example.com", "Invoice Due", "Please settle Rs 50,000")
    assert res["status"] == "mock_sent"
    assert "Mock email recorded" in res["message"]
    assert res["to"] == "customer@example.com"
    assert res["mailto"] is not None


def test_send_email_invalid_email():
    res = send_email("invalid-email", "Sub", "Body")
    assert res["status"] == "failed"
    assert "Invalid recipient" in res["error"]


def test_send_email_live_smtp(monkeypatch):
    mock_smtp_cls = MagicMock()
    mock_instance = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_instance

    with patch("smtplib.SMTP", mock_smtp_cls):
        res = send_email(
            "client@example.com",
            "Urgent Payment",
            "Details here",
            config={
                "host": "smtp.example.com",
                "port": 587,
                "user": "alerts@example.com",
                "password": "pass",
            },
        )
        assert res["status"] == "sent"
        assert mock_instance.starttls.called
        assert mock_instance.login.called
        assert mock_instance.send_message.called
