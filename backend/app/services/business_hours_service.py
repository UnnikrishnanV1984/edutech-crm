"""Business-hours-aware SLA clock math — the one piece of PHASE_3_PLAN.md
with genuine algorithmic risk (off-by-one across a day/holiday boundary),
kept as one small, directly-unit-testable function rather than inlined
into the Celery task (PHASE_3_PLAN.md §6).

Takes plain primitives (dict/list/str), not the tenant_sla_settings ORM
row, so it has no DB/schema coupling and is trivial to unit test.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

DEFAULT_BUSINESS_HOURS: dict[str, list[list[str]]] = {
    "mon": [["09:00", "18:00"]],
    "tue": [["09:00", "18:00"]],
    "wed": [["09:00", "18:00"]],
    "thu": [["09:00", "18:00"]],
    "fri": [["09:00", "18:00"]],
    "sat": [],
    "sun": [],
}

_MAX_DAYS_SCANNED = 3650  # ~10 years — an all-empty schedule is a config bug, not a valid state


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def add_business_minutes(
    start: datetime,
    minutes: int,
    business_hours: dict[str, list[list[str]]],
    holidays: list[str],
    timezone: str,
) -> datetime:
    """Returns `start` advanced by `minutes` of business time, honoring
    `business_hours` (day-of-week -> list of [start, end] "HH:MM" windows,
    tenant-local) and `holidays` (list of "YYYY-MM-DD" dates, entirely
    skipped regardless of business_hours). `start` may be any aware
    datetime; the result is returned in UTC."""
    tz = ZoneInfo(timezone)
    holiday_set = set(holidays)
    cursor = start.astimezone(tz)
    remaining = minutes

    for _ in range(_MAX_DAYS_SCANNED):
        if remaining <= 0:
            break
        day_key = DAY_KEYS[cursor.weekday()]
        is_holiday = cursor.date().isoformat() in holiday_set
        windows = [] if is_holiday else business_hours.get(day_key, [])

        advanced_today = False
        for window_start_str, window_end_str in windows:
            window_start = datetime.combine(cursor.date(), _parse_time(window_start_str), tzinfo=tz)
            window_end = datetime.combine(cursor.date(), _parse_time(window_end_str), tzinfo=tz)
            if cursor < window_start:
                cursor = window_start
            if cursor >= window_end:
                continue
            available_minutes = (window_end - cursor).total_seconds() / 60
            if available_minutes >= remaining:
                cursor = cursor + timedelta(minutes=remaining)
                remaining = 0
            else:
                cursor = window_end
                remaining -= available_minutes
            advanced_today = True
            break

        if not advanced_today:
            next_day = cursor.date() + timedelta(days=1)
            cursor = datetime.combine(next_day, time(0, 0), tzinfo=tz)
    else:
        raise ValueError(
            "business_hours configuration yields no working time within "
            f"{_MAX_DAYS_SCANNED} days — check for an all-empty schedule"
        )

    return cursor.astimezone(ZoneInfo("UTC"))
