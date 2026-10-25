"""Delivery module for reminder and alert notifications (SMTP, WhatsApp, SMS).

Input: Recipient details (email/phone), subject, message body, optional SMTP config.
Output: Status dict with delivery outcome, transmission links, or mock confirmation.
"""
from __future__ import annotations

import os
import re
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote


def normalize_indian_phone(phone: str | None) -> str | None:
    """Normalize phone number to Indian standard format (91XXXXXXXXXX).

    Args:
        phone: Raw phone string (e.g. "+91 98765 43210", "09876543210", "9876543210").

    Returns:
        Normalized digits string (e.g. "919876543210") or None if invalid.
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return digits if digits else None


def build_whatsapp_link(phone: str | None, text: str) -> str | None:
    """Build a wa.me click-to-chat URL with pre-filled message text.

    Args:
        phone: Customer phone number.
        text: Pre-rendered message text.

    Returns:
        Full wa.me URL or None if phone is missing.
    """
    normalized = normalize_indian_phone(phone)
    if not normalized:
        return None
    return f"https://wa.me/{normalized}?text={quote(text)}"


def build_sms_link(phone: str | None, text: str) -> str | None:
    """Build a system sms: URI for mobile messaging.

    Args:
        phone: Customer phone number.
        text: Pre-rendered message text.

    Returns:
        sms: URI string or None if phone is missing.
    """
    normalized = normalize_indian_phone(phone)
    if not normalized:
        return None
    return f"sms:{normalized}?body={quote(text)}"


def build_mailto_link(email: str | None, subject: str, text: str) -> str | None:
    """Build a mailto: link as a fallback if automated SMTP is not available.

    Args:
        email: Recipient email address.
        subject: Email subject line.
        text: Email body text.

    Returns:
        mailto: URI string or None if email is missing.
    """
    if not email:
        return None
    return f"mailto:{email}?subject={quote(subject)}&body={quote(text)}"


def send_email(
    to_email: str,
    subject: str,
    body: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send an email using SMTP with STARTTLS or return a clearly labeled mock delivery.

    Args:
        to_email: Recipient email address.
        subject: Subject line.
        body: Text content.
        config: Optional dict overriding env vars (host, port, user, password, from_email).

    Returns:
        dict with status ('sent', 'mock_sent', or 'failed'), message, and mailto fallback.
    """
    if not to_email or "@" not in to_email:
        return {
            "status": "failed",
            "error": "Invalid recipient email address",
            "to": to_email,
            "mailto": None,
            "copy_text": f"Subject: {subject}\n\n{body}",
        }

    cfg = config or {}
    smtp_host = cfg.get("host") or os.environ.get("SMTP_HOST")
    smtp_port = int(cfg.get("port") or os.environ.get("SMTP_PORT", 587))
    smtp_user = cfg.get("user") or os.environ.get("SMTP_USER")
    smtp_password = cfg.get("password") or os.environ.get("SMTP_PASSWORD")
    smtp_from = cfg.get("from_email") or os.environ.get("SMTP_FROM") or smtp_user or "noreply@cashflow.local"
    mock_mode = os.environ.get("MOCK_DELIVERY", "false").lower() in ("true", "1")

    mailto = build_mailto_link(to_email, subject, body)
    copy_text = f"Subject: {subject}\n\n{body}"

    # If SMTP is unconfigured or mock mode is requested, use mock delivery
    if mock_mode or not smtp_host:
        return {
            "status": "mock_sent",
            "message": "Mock email recorded. SMTP not configured on server (configure SMTP_HOST in backend/.env for live dispatch).",
            "to": to_email,
            "from": smtp_from,
            "subject": subject,
            "body": body,
            "mailto": mailto,
            "copy_text": copy_text,
        }

    # Attempt live SMTP delivery
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            try:
                server.starttls()
                server.ehlo()
            except Exception:
                # Server may not support STARTTLS or already be secure
                pass
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return {
            "status": "sent",
            "message": f"Email delivered successfully to {to_email} via {smtp_host}.",
            "to": to_email,
            "from": smtp_from,
            "subject": subject,
            "mailto": mailto,
        }
    except Exception as err:
        return {
            "status": "failed",
            "error": f"SMTP dispatch failed: {err}",
            "to": to_email,
            "from": smtp_from,
            "subject": subject,
            "mailto": mailto,
            "copy_text": copy_text,
        }
