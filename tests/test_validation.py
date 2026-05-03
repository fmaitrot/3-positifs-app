from datetime import date, timedelta

from positives.validation import (
    is_not_future_iso_date,
    is_valid_iso_date,
    normalize_email,
    parse_bounded_int,
    validate_email,
    validate_items,
    validate_month,
    validate_password,
    validate_reminder_time,
)


def test_is_valid_iso_date_accepts_expected_format() -> None:
    assert is_valid_iso_date("2026-04-30")


def test_is_valid_iso_date_rejects_invalid_format() -> None:
    assert not is_valid_iso_date("30-04-2026")


def test_validate_items_accepts_three_non_empty_values() -> None:
    ok, message, normalized = validate_items(["  a", "b  ", " c "])
    assert ok is True
    assert message == ""
    assert normalized == ["a", "b", "c"]


def test_validate_items_rejects_wrong_count() -> None:
    ok, message, _ = validate_items(["a", "b"])
    assert ok is False
    assert message == "items must be an array of 3 values"


def test_validate_items_rejects_empty_value() -> None:
    ok, message, _ = validate_items(["a", "", "c"])
    assert ok is False
    assert message == "all 3 positive items are required"


def test_parse_bounded_int_applies_default_and_bounds() -> None:
    assert parse_bounded_int(None, default=10, min_value=1, max_value=100) == 10
    assert parse_bounded_int("invalid", default=10, min_value=1, max_value=100) == 10
    assert parse_bounded_int("0", default=10, min_value=1, max_value=100) == 1
    assert parse_bounded_int("101", default=10, min_value=1, max_value=100) == 100
    assert parse_bounded_int("42", default=10, min_value=1, max_value=100) == 42


def test_is_not_future_iso_date_rejects_future_date() -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert is_not_future_iso_date(tomorrow) is False


def test_is_not_future_iso_date_accepts_today() -> None:
    assert is_not_future_iso_date(date.today().isoformat()) is True


def test_validate_email_normalizes_and_validates_value() -> None:
    ok, value = validate_email("  USER@example.com ")
    assert ok is True
    assert value == "user@example.com"
    assert normalize_email("  USER@example.com ") == "user@example.com"


def test_validate_email_rejects_invalid_format() -> None:
    ok, message = validate_email("invalid")
    assert ok is False
    assert message == "invalid email format"


def test_validate_password_bounds() -> None:
    ok_short, message_short = validate_password("short")
    assert ok_short is False
    assert message_short == "password must contain at least 8 characters"

    ok_valid, value_valid = validate_password("long-enough")
    assert ok_valid is True
    assert value_valid == "long-enough"


def test_validate_month_format() -> None:
    ok, month_value = validate_month("2026-04")
    assert ok is True
    assert month_value == "2026-04"

    ok_invalid, error_message = validate_month("2026-13")
    assert ok_invalid is False
    assert error_message == "invalid month format"


def test_validate_reminder_time_format() -> None:
    ok, value = validate_reminder_time("21:30")
    assert ok is True
    assert value == "21:30"

    ok_invalid, error_message = validate_reminder_time("25:99")
    assert ok_invalid is False
    assert error_message == "invalid reminder time format"
