"""PHASE_3_PLAN.md §6/§9 step 7 — add_business_minutes' unit tests, the
one piece of the SLA engine with genuine algorithmic risk."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.business_hours_service import DEFAULT_BUSINESS_HOURS, add_business_minutes

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")

MON_09_18 = DEFAULT_BUSINESS_HOURS  # mon-fri 09:00-18:00, sat/sun empty


def test_same_day_stays_within_the_window():
    start = datetime(2026, 1, 5, 10, 0, tzinfo=IST)  # Monday
    result = add_business_minutes(start, 60, MON_09_18, [], "Asia/Kolkata")
    assert result.astimezone(IST) == datetime(2026, 1, 5, 11, 0, tzinfo=IST)


def test_crosses_a_day_boundary():
    start = datetime(2026, 1, 5, 17, 30, tzinfo=IST)  # Monday, 30 min left today
    result = add_business_minutes(start, 60, MON_09_18, [], "Asia/Kolkata")
    assert result.astimezone(IST) == datetime(2026, 1, 6, 9, 30, tzinfo=IST)  # Tuesday


def test_crosses_a_weekend():
    start = datetime(2026, 1, 9, 17, 30, tzinfo=IST)  # Friday, 30 min left today
    result = add_business_minutes(start, 60, MON_09_18, [], "Asia/Kolkata")
    assert result.astimezone(IST) == datetime(2026, 1, 12, 9, 30, tzinfo=IST)  # Monday


def test_crosses_a_holiday():
    start = datetime(2026, 1, 5, 17, 30, tzinfo=IST)  # Monday, 30 min left today
    result = add_business_minutes(start, 60, MON_09_18, ["2026-01-06"], "Asia/Kolkata")
    assert result.astimezone(IST) == datetime(2026, 1, 7, 9, 30, tzinfo=IST)  # Wed, Tue skipped


def test_respects_tenant_timezone_not_utc():
    # 2026-01-05T20:00 UTC = 15:00 EST — within business hours in New York,
    # but the raw UTC hour (20) would read as outside a 09-18 window if
    # the function ever mishandled timezone conversion.
    start = datetime(2026, 1, 5, 20, 0, tzinfo=UTC)
    result = add_business_minutes(start, 60, MON_09_18, [], "America/New_York")
    assert result.astimezone(NY) == datetime(2026, 1, 5, 16, 0, tzinfo=NY)
    assert result.astimezone(UTC) == datetime(2026, 1, 5, 21, 0, tzinfo=UTC)


def test_split_windows_within_a_day():
    lunch_break = {**MON_09_18, "mon": [["09:00", "13:00"], ["14:00", "18:00"]]}
    start = datetime(2026, 1, 5, 12, 30, tzinfo=IST)  # Monday, 30 min left before lunch
    result = add_business_minutes(start, 60, lunch_break, [], "Asia/Kolkata")
    # 30 min consumed to 13:00, remaining 30 min jumps the lunch gap to 14:00-14:30.
    assert result.astimezone(IST) == datetime(2026, 1, 5, 14, 30, tzinfo=IST)


def test_zero_minutes_returns_start_unchanged():
    start = datetime(2026, 1, 5, 10, 0, tzinfo=IST)
    result = add_business_minutes(start, 0, MON_09_18, [], "Asia/Kolkata")
    assert result.astimezone(IST) == start
