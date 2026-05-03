import re
from datetime import date
from typing import Any

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_iso_date(date_value: str) -> bool:
    return bool(DATE_PATTERN.match(date_value))


def validate_items(items: Any) -> tuple[bool, str, list[str]]:
    if not isinstance(items, list) or len(items) != 3:
        return False, "items must be an array of 3 values", []

    normalized = [str(item or "").strip() for item in items]

    if any(len(item) == 0 for item in normalized):
        return False, "all 3 positive items are required", []

    if any(len(item) > 200 for item in normalized):
        return False, "each item must be 200 characters max", []

    return True, "", normalized


def parse_bounded_int(raw_value: Any, default: int, min_value: int, max_value: int) -> int:
    if raw_value is None:
        return default

    try:
        parsed = int(str(raw_value))
    except ValueError:
        return default

    if parsed < min_value:
        return min_value

    if parsed > max_value:
        return max_value

    return parsed


def is_not_future_iso_date(date_value: str) -> bool:
    try:
        parsed = date.fromisoformat(date_value)
    except ValueError:
        return False
    return parsed <= date.today()


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def validate_email(value: Any) -> tuple[bool, str]:
    email = normalize_email(value)
    if not email:
        return False, "email is required"
    if len(email) > 320 or not EMAIL_PATTERN.match(email):
        return False, "invalid email format"
    return True, email


def validate_password(value: Any) -> tuple[bool, str]:
    password = str(value or "")
    if len(password) < 8:
        return False, "password must contain at least 8 characters"
    if len(password) > 128:
        return False, "password is too long"
    return True, password


def validate_month(value: Any) -> tuple[bool, str]:
    month_value = str(value or "").strip()
    if not MONTH_PATTERN.match(month_value):
        return False, "invalid month format"
    year, month = month_value.split("-")
    month_number = int(month)
    if month_number < 1 or month_number > 12:
        return False, "invalid month format"
    _ = int(year)
    return True, month_value


def validate_reminder_time(value: Any) -> tuple[bool, str]:
    time_value = str(value or "").strip()
    if not TIME_PATTERN.match(time_value):
        return False, "invalid reminder time format"

    hours, minutes = time_value.split(":")
    hour_value = int(hours)
    minute_value = int(minutes)
    if hour_value > 23 or minute_value > 59:
        return False, "invalid reminder time format"

    return True, time_value
