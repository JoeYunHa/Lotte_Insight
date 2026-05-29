"""
Collect Lotte Giants game schedule and results from the official website.
Stores daily game data in the `games` table.
"""

import logging
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from core.config import settings
from core.database import supabase

logger = logging.getLogger(__name__)

_CALENDAR_URL = "https://www.giantsclub.com/m/?pcode=505&type=calendar&flag=1&y={year}&m={month}"
_HOME_VENUE = "사직"
_RESULT_VALUES = {"승", "패", "무"}


def _parse_score(raw: str) -> str | None:
    raw = raw.strip()
    if ":" not in raw:
        return None
    parts = [p.strip() for p in raw.split(":")]
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    return f"{parts[0]}-{parts[1]}"


def _parse_date(day_text: str, year: int, month: int) -> str | None:
    match = re.match(r"\d{2}\.(\d{2})", day_text.strip())
    if not match:
        return None
    day = int(match.group(1))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def fetch_month_games(year: int, month: int) -> list[dict]:
    url = _CALENDAR_URL.format(year=year, month=month)
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": settings.crawl_user_agent})
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
    except requests.Timeout as exc:
        logger.error("Timeout requesting giantsclub calendar (year=%d month=%d): %s", year, month, exc)
        return []
    except requests.ConnectionError as exc:
        logger.error("Connection error to giantsclub calendar (year=%d month=%d): %s", year, month, exc)
        return []
    except requests.HTTPError as exc:
        logger.error("HTTP error from giantsclub calendar (year=%d month=%d): %s", year, month, exc)
        return []
    except requests.RequestException as exc:
        logger.error("Request failure for giantsclub calendar (year=%d month=%d): %s", year, month, exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table")
    if not table:
        logger.warning("Calendar table not found")
        return []

    games: list[dict] = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue

        date_str = _parse_date(tds[0].get_text(strip=True), year, month)
        if not date_str:
            continue

        img = tds[1].find("img")
        opponent = img.get("alt", "").split()[0] if img else tds[1].get_text(strip=True)
        if not opponent:
            continue

        venue = tds[2].get_text(strip=True)
        game_time = tds[3].get_text(strip=True) or None
        score = _parse_score(tds[4].get_text(strip=True))
        result_raw = tds[5].get_text(strip=True)
        result = result_raw if result_raw in _RESULT_VALUES else None

        games.append(
            {
                "date": date_str,
                "opponent": opponent,
                "venue": venue,
                "home_away": "home" if venue == _HOME_VENUE else "away",
                "game_time": game_time,
                "score": score,
                "result": result,
            }
        )

    logger.info("Parsed %d games for year=%d month=%d", len(games), year, month)
    return games


def sync_game(target_date: date) -> dict | None:
    games = fetch_month_games(target_date.year, target_date.month)
    target_iso = target_date.isoformat()
    day_games = [g for g in games if g["date"] == target_iso]
    if not day_games:
        logger.info("No game found for date: %s", target_iso)
        return None

    sorted_games = sorted(
        day_games,
        key=lambda x: (
            0 if x.get("game_time") else 1,
            x.get("game_time") or "99:99",
            x.get("opponent") or "",
        ),
    )

    upsert_rows: list[dict] = []
    for idx, game in enumerate(sorted_games, start=1):
        row = dict(game)
        row["game_seq"] = idx
        upsert_rows.append(row)

    supabase.table("games").upsert(upsert_rows, on_conflict="date,game_seq").execute()

    if len(upsert_rows) > 1:
        logger.info("Saved %d games for %s (doubleheader supported)", len(upsert_rows), target_iso)
    else:
        logger.info(
            "Saved game: %s vs %s (%s)",
            target_iso,
            upsert_rows[0]["opponent"],
            upsert_rows[0].get("result") or "scheduled",
        )
    return upsert_rows[0]


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print(sync_game(target))
