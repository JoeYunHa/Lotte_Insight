from datetime import date, timedelta


def utc_day_bounds(target_date: date) -> tuple[str, str]:
    """Return ISO-8601 UTC strings spanning the full KST calendar day.

    KST = UTC+9, so KST 00:00 is UTC 15:00 of the *previous* day.
    """
    prev = target_date - timedelta(days=1)
    return (
        f"{prev.isoformat()}T15:00:00+00:00",
        f"{target_date.isoformat()}T14:59:59.999999+00:00",
    )
