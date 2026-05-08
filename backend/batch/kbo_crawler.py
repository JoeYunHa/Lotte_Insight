"""
Collect KBO player stats for the configured team and store them in player_stats_daily.
"""

import logging
import re
from datetime import date
from typing import TYPE_CHECKING
from urllib.robotparser import RobotFileParser

import requests as http
from bs4 import BeautifulSoup

try:
    from core.bootstrap import load_player_name_to_id_map, load_settings, load_supabase
except ModuleNotFoundError:
    from backend.core.bootstrap import (
        load_player_name_to_id_map,
        load_settings,
        load_supabase,
    )

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)

KBO_BASE_URL = "https://www.koreabaseball.com"
URLS = {
    "hitter_basic1": f"{KBO_BASE_URL}/Record/Player/HitterBasic/Basic1.aspx",
    "hitter_basic2": f"{KBO_BASE_URL}/Record/Player/HitterBasic/Basic2.aspx",
    "pitcher_basic1": f"{KBO_BASE_URL}/Record/Player/PitcherBasic/Basic1.aspx",
}
TEAM_SELECTORS = [
    'select[name*="ddlTeam"]',
    'select[name*="ddlSearchTeam"]',
    'select[name*="ddlTeamCode"]',
]
NAV_TIMEOUT_MS = 30_000
SELECT_TIMEOUT_MS = 10_000
STAT_MAP = {
    "hitter_basic1": {
        "HRA_RT": "avg",
        "GAME_CN": "g",
        "PA_CN": "pa",
        "AB_CN": "ab",
        "HIT_CN": "h",
        "HR_CN": "hr",
        "RBI_CN": "rbi",
        "SH_CN": "sh",
        "SF_CN": "sf",
    },
    "hitter_basic2": {
        "OBP_RT": "obp",
        "SLG_RT": "slg",
        "OPS_RT": "ops",
        "BB_CN": "bb",
        "KK_CN": "so",
    },
    "pitcher_basic1": {
        "ERA_RT": "era",
        "WHIP_RT": "whip",
        "GAME_CN": "g",
        "W_CN": "w",
        "L_CN": "l",
        "SV_CN": "sv",
        "HOLD_CN": "hold",
        "KK_CN": "so",
        "BB_CN": "bb",
    },
}

_robot_parser_instance: RobotFileParser | None = None
settings = load_settings()

REGISTER_URL = f"{KBO_BASE_URL}/Player/Register.aspx"
REGISTER_TEAM_FIELD = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$hfSearchTeam"
REGISTER_DATE_FIELD = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$hfSearchDate"
REGISTER_EVENT_TARGET = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$btnCalendarSelect"
STAFF_SECTIONS = {"감독", "코치"}

# Backward-compatible aliases for local tooling/tests.
_URLS = URLS
_STAT_MAP = STAT_MAP
_REGISTER_URL = REGISTER_URL
_REG_TEAM_FIELD = REGISTER_TEAM_FIELD
_REG_DATE_FIELD = REGISTER_DATE_FIELD
_REG_EVENT_TARGET = REGISTER_EVENT_TARGET


def _robot_parser() -> RobotFileParser:
    global _robot_parser_instance
    if _robot_parser_instance is None:
        parser = RobotFileParser()
        parser.set_url(f"{KBO_BASE_URL}/robots.txt")
        try:
            parser.read()
        except Exception as exc:
            logger.warning("Failed to read robots.txt, continuing cautiously: %s", exc)
        _robot_parser_instance = parser
    return _robot_parser_instance


def _can_fetch(url: str) -> bool:
    return _robot_parser().can_fetch(settings.crawl_user_agent, url)


def _select_team_and_get_html(
    page: "Page",
    url: str,
    *,
    wait_until: str = "networkidle",
) -> str | None:
    if not _can_fetch(url):
        logger.warning("Blocked by robots.txt: %s", url)
        return None

    try:
        page.goto(url, wait_until=wait_until, timeout=NAV_TIMEOUT_MS)
        page.wait_for_selector("table tbody tr", timeout=SELECT_TIMEOUT_MS)
    except Exception as exc:
        logger.error("Failed to load page %s: %s", url, exc)
        return None

    for selector in TEAM_SELECTORS:
        try:
            page.select_option(selector, settings.team_code)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            page.wait_for_selector("table tbody tr", timeout=SELECT_TIMEOUT_MS)
            return page.content()
        except Exception:
            continue

    logger.warning("Could not select team on page: %s", url)
    return None


def _safe_float(text: str) -> float | None:
    text = text.strip()
    if text in ("", "-", "."):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_table(html: str, stat_map: dict[str, str]) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    tbody = soup.select_one("table tbody")
    if not tbody:
        logger.warning("Missing table body in stats page")
        return []

    rows: list[dict] = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4 or not tds[0].get_text(strip=True).isdigit():
            continue

        player_link = tds[1].find("a")
        if not player_link:
            continue

        team = tds[2].get_text(strip=True)
        if team != settings.team_name_ko:
            continue

        match = re.search(r"playerId=(\d+)", player_link.get("href", ""))
        stats: dict = {
            "name": player_link.get_text(strip=True),
            "kbo_player_id": match.group(1) if match else "",
        }
        for td in tds:
            data_id = td.get("data-id", "")
            if data_id in stat_map:
                stats[stat_map[data_id]] = _safe_float(td.get_text(strip=True))
        rows.append(stats)

    return rows


def _extract_update_panel(text: str) -> str:
    if "|updatePanel|" not in text:
        return text

    parts: list[str] = []
    pos = 0
    while pos < len(text):
        pipe1 = text.find("|", pos)
        if pipe1 < 0:
            break
        try:
            length = int(text[pos:pipe1])
        except ValueError:
            break
        pipe2 = text.find("|", pipe1 + 1)
        if pipe2 < 0:
            break
        response_type = text[pipe1 + 1:pipe2]
        pipe3 = text.find("|", pipe2 + 1)
        if pipe3 < 0:
            break
        content_start = pipe3 + 1
        if response_type == "updatePanel":
            parts.append(text[content_start:content_start + length])
        pos = content_start + length + 1
    return "\n".join(parts) if parts else text


def _parse_register_names(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    names: list[str] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        header_cells = rows[0].find_all(["td", "th"])
        if len(header_cells) < 2:
            continue
        section = header_cells[1].get_text(strip=True)
        if section in STAFF_SECTIONS:
            continue

        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            if int(cells[0].get("colspan", 1)) > 1:
                continue
            if not cells[0].get_text(strip=True).isdigit():
                continue
            player_link = cells[1].find("a")
            name = (
                player_link.get_text(strip=True)
                if player_link
                else cells[1].get_text(strip=True)
            )
            if name:
                names.append(name)

    return names


def fetch_roster() -> list[str]:
    if not _can_fetch(REGISTER_URL):
        logger.warning("Blocked by robots.txt: %s", REGISTER_URL)
        return []

    session = http.Session()
    session.headers.update(
        {"User-Agent": settings.crawl_user_agent, "Referer": REGISTER_URL}
    )

    try:
        response = session.get(REGISTER_URL, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        def hidden(name: str) -> str:
            element = soup.find("input", {"name": name})
            return element.get("value", "") if element else ""

        search_date = hidden(REGISTER_DATE_FIELD) or date.today().strftime("%Y%m%d")
        post_data = {
            "__VIEWSTATE": hidden("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": hidden("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": hidden("__EVENTVALIDATION"),
            "__EVENTTARGET": REGISTER_EVENT_TARGET,
            "__EVENTARGUMENT": "",
            REGISTER_TEAM_FIELD: settings.team_code,
            REGISTER_DATE_FIELD: search_date,
        }

        response2 = session.post(REGISTER_URL, data=post_data, timeout=30)
        response2.raise_for_status()
        response2.encoding = response2.apparent_encoding

        html = _extract_update_panel(response2.text)
        names = _parse_register_names(html)
        logger.info("Fetched roster from register page: %s players", len(names))
        return sorted(names)
    except Exception as exc:
        logger.error("Failed to fetch register roster: %s", exc)
        return []


def run(target_date: date | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    today = target_date or date.today()
    logger.info("KBO stat collection started: %s", today)

    supabase = load_supabase()
    player_map = load_player_name_to_id_map()
    merged: dict[str, dict] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=settings.crawl_user_agent)

        for page_key, url in URLS.items():
            html = _select_team_and_get_html(page, url)
            if not html:
                continue
            rows = _parse_table(html, STAT_MAP[page_key])
            logger.info("Parsed %s rows from %s", len(rows), page_key)
            for row in rows:
                entry = merged.setdefault(
                    row["name"],
                    {"kbo_player_id": row.get("kbo_player_id", "")},
                )
                entry.update(row)

        browser.close()

    upsert_rows: list[dict] = []
    unmatched: list[str] = []

    for name, stats in merged.items():
        player_id = player_map.get(name)
        if not player_id:
            unmatched.append(name)
            continue

        raw_stats = {key: value for key, value in stats.items() if key != "name"}
        upsert_rows.append(
            {
                "player_id": player_id,
                "date": today.isoformat(),
                "avg": stats.get("avg"),
                "ops": stats.get("ops"),
                "era": stats.get("era"),
                "raw_stats": raw_stats,
            }
        )

    if upsert_rows:
        supabase.table("player_stats_daily").upsert(
            upsert_rows,
            on_conflict="player_id,date",
        ).execute()

    if unmatched:
        logger.warning("Unmatched players: %s", unmatched)

    result = {
        "saved": len(upsert_rows),
        "unmatched": len(unmatched),
        "date": today.isoformat(),
    }
    logger.info("KBO stat collection completed: %s", result)
    return result


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, default=None)
    args = parser.parse_args()

    print(run(args.date))
    sys.exit(0)
