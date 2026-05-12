from datetime import date


def utc_day_bounds(target_date: date) -> tuple[str, str]:
    day = target_date.isoformat()
    return (f"{day}T00:00:00+00:00", f"{day}T23:59:59.999999+00:00")
