"""
Collect Lotte Giants game schedule and results from the official website.
Stores results in the `games` table (upsert on date).
"""

import logging
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from core.config import settings
from core.database import supabase

logger = logging.getLogger(__name__)

_CALENDAR_URL = (
    "https://www.giantsclub.com/m/?pcode=505&type=calendar&flag=1&y={year}&m={month}"
)
_HOME_VENUE = "사직"
_RESULT_VALUES = {"승", "패", "무"}


def _parse_score(raw: str) -> str | None:
    """'10 : 7' → '10-7', 그 외 → None."""
    raw = raw.strip()
    if ":" in raw:
        parts = [p.strip() for p in raw.split(":")]
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            return f"{parts[0]}-{parts[1]}"
    return None


def _parse_date(day_text: str, year: int, month: int) -> str | None:
    """'05.01(금)' → '2026-05-01'"""
    m = re.match(r"\d{2}\.(\d{2})", day_text.strip())
    if not m:
        return None
    day = int(m.group(1))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def fetch_month_games(year: int, month: int) -> list[dict]:
    url = _CALENDAR_URL.format(year=year, month=month)
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": settings.crawl_user_agent},
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
    except Exception as exc:
        logger.error("giantsclub.com 요청 실패: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table")
    if not table:
        logger.warning("giantsclub.com: 경기 테이블을 찾을 수 없음")
        return []

    games: list[dict] = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue

        date_str = _parse_date(tds[0].get_text(strip=True), year, month)
        if not date_str:
            continue

        # 상대팀: img alt 또는 텍스트
        img = tds[1].find("img")
        opponent = img.get("alt", "").split()[0] if img else tds[1].get_text(strip=True)
        if not opponent:
            continue

        venue = tds[2].get_text(strip=True)
        game_time = tds[3].get_text(strip=True) or None
        score_raw = tds[4].get_text(strip=True)
        result_raw = tds[5].get_text(strip=True)

        score = _parse_score(score_raw)
        result = result_raw if result_raw in _RESULT_VALUES else None
        home_away = "홈" if venue == _HOME_VENUE else "원정"

        games.append({
            "date": date_str,
            "opponent": opponent,
            "venue": venue,
            "home_away": home_away,
            "game_time": game_time,
            "score": score,
            "result": result,
        })

    logger.info("giantsclub.com: %d경기 파싱 완료 (y=%d m=%d)", len(games), year, month)
    return games


def sync_game(target_date: date) -> dict | None:
    """target_date의 경기를 games 테이블에 upsert. 경기 없으면 None 반환."""
    games = fetch_month_games(target_date.year, target_date.month)
    target_iso = target_date.isoformat()
    game = next((g for g in games if g["date"] == target_iso), None)
    if not game:
        logger.info("경기 없음: %s", target_iso)
        return None

    supabase.table("games").upsert(game, on_conflict="date").execute()
    logger.info("경기 저장: %s vs %s (%s)", target_iso, game["opponent"], game.get("result") or "경기전")
    return game


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    result = sync_game(target)
    print(result)
