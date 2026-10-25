"""Clock utility for Asia/Kolkata timezone and cash freshness checks.

Input: None or last_updated date/ISO string.
Output: date or bool.
All time-dependent services and tests use today_ist() so they can be deterministically patched.
"""

from __future__ import annotations

from datetime import date, datetime
import os
from zoneinfo import ZoneInfo

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")


def today_ist() -> date:
    """Returns today's date in Asia/Kolkata timezone. Can be monkeypatched in tests."""
    override = os.environ.get('APP_FAKE_TODAY')
    if override and os.environ.get('APP_ENV', 'development') != 'production':
        return date.fromisoformat(override)
    return datetime.now(KOLKATA_TZ).date()


def is_stale(last_updated: date | str | None, max_days: int = 3) -> bool:
    """Checks whether the cash last_updated date is older than max_days relative to today_ist().

    Args:
        last_updated: ISO string (YYYY-MM-DD or full timestamp), date object, or None.
        max_days: Number of days threshold before marking as stale (default: 3).

    Returns:
        bool: True if last_updated is missing or older than max_days, False otherwise.
    """
    if last_updated is None:
        return True

    if isinstance(last_updated, str):
        try:
            # Handle ISO string with potential time component
            clean = last_updated.split("T")[0].strip()
            parsed = date.fromisoformat(clean)
        except (ValueError, TypeError):
            return True
    elif isinstance(last_updated, date):
        parsed = last_updated
    else:
        return True

    today = today_ist()
    return (today - parsed).days > max_days
