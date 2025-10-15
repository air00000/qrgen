"""Utility helpers for working with simple time strings."""

from __future__ import annotations


def normalize_hhmm(value: str | None) -> str | None:
    """Return a HH:MM formatted string or ``None`` if the input is invalid.

    The helper trims whitespace, allows one- or two-digit hours, and ensures the
    resulting time fits into a 24-hour clock. Minutes must always be provided as
    two digits. Any invalid input returns ``None`` so callers can decide how to
    handle the error (e.g. show a message or fall back to the current time).
    """

    if value is None:
        return None

    value = value.strip()
    if not value or ":" not in value:
        return None

    hours, minutes = value.split(":", 1)
    if not (hours.isdigit() and minutes.isdigit() and len(minutes) == 2):
        return None

    hour_value = int(hours)
    minute_value = int(minutes)
    if not (0 <= hour_value <= 23 and 0 <= minute_value <= 59):
        return None

    return f"{hour_value:02d}:{minute_value:02d}"
