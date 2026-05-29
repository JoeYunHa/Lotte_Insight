from datetime import date

from fastapi import APIRouter, Query

from core import cache
from core.time_utils import today_kst
from services import home_service
from services.cache_keys import CacheKeyBuilder

router = APIRouter()


@router.get("/home")
def get_home_report(report_date: date | None = Query(default=None)):
    today = today_kst()
    target = report_date or today

    cache_key = CacheKeyBuilder.home_report(report_date=target)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    result = home_service.build_home_report(target)

    # Only cache when data is meaningful. For today's snapshot, both a team
    # report and a non-zero article count must be present — otherwise we'd
    # freeze a partial snapshot before downstream batch jobs complete.
    is_today_or_future = target >= today
    has_complete_data = (
        result.get("team_report") is not None and result.get("article_count", 0) > 0
    )
    if not is_today_or_future or has_complete_data:
        cache.set_json(cache_key, result, ttl=cache.ttl_seconds(target))
    return result
