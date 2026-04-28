"""
KBO 공식 사이트에서 롯데 자이언츠 선수 시즌 누적 기록을 수집하여
player_stats_daily 테이블에 저장한다.

KBO 사이트는 JavaScript로 테이블을 렌더링하므로 Playwright 헤드리스
브라우저로 드롭다운을 직접 조작한 뒤 HTML을 추출한다.

수집 대상:
  타자 Basic1 (HRA_RT → avg)  +  Basic2 (OPS_RT → ops)
  투수 Basic1 (ERA_RT → era,  WHIP_RT → whip)

사용:
    python batch/kbo_crawler.py          # 오늘 날짜로 저장
    python batch/kbo_crawler.py --date 2026-04-28
"""

import logging
import re
from datetime import date
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright

from core.config import settings
from core.database import supabase

logger = logging.getLogger(__name__)

# ── 상수 ─────────────────────────────────────────────────────────────────────

_KBO_BASE = "https://www.koreabaseball.com"

_URLS = {
    "hitter_basic1":  f"{_KBO_BASE}/Record/Player/HitterBasic/Basic1.aspx",
    "hitter_basic2":  f"{_KBO_BASE}/Record/Player/HitterBasic/Basic2.aspx",
    "pitcher_basic1": f"{_KBO_BASE}/Record/Player/PitcherBasic/Basic1.aspx",
}

# 선수명만 추출할 보충 stats 페이지 (stat_map 불필요)
_SUPPLEMENT_URLS = [
    f"{_KBO_BASE}/Record/Player/HitterBasic/Basic3.aspx",
    f"{_KBO_BASE}/Record/Player/PitcherBasic/Basic2.aspx",
    f"{_KBO_BASE}/Record/Player/PitcherBasic/Basic3.aspx",
]

# 1군 등록선수 현황 후보 URL — 사이트 구조 변경 대비 복수 관리
_ACTIVE_ROSTER_URLS = [
    f"{_KBO_BASE}/Team/Roster/ActiveRoster.aspx",
    f"{_KBO_BASE}/TeamInfo/Player.aspx",
]

# ddlTeam 셀렉터 후보 — 페이지마다 name 속성이 다를 수 있음
_TEAM_SELECTORS = [
    'select[name*="ddlTeam"]',
    'select[name*="ddlSearchTeam"]',
    'select[name*="ddlTeamCode"]',
]

_LOTTE_CODE = "LT"
_NAV_TIMEOUT = 30_000   # ms — 페이지 로드 대기
_SEL_TIMEOUT = 10_000   # ms — 테이블 출현 대기

# 수집할 stat 컬럼: {page_key: {data-id: 내부 키}}
_STAT_MAP = {
    "hitter_basic1": {
        "HRA_RT":  "avg",
        "GAME_CN": "g",
        "PA_CN":   "pa",
        "AB_CN":   "ab",
        "HIT_CN":  "h",
        "HR_CN":   "hr",
        "RBI_CN":  "rbi",
        "SH_CN":   "sh",
        "SF_CN":   "sf",
    },
    "hitter_basic2": {
        "OBP_RT":  "obp",
        "SLG_RT":  "slg",
        "OPS_RT":  "ops",
        "BB_CN":   "bb",
        "KK_CN":   "so",
    },
    "pitcher_basic1": {
        "ERA_RT":  "era",
        "WHIP_RT": "whip",
        "GAME_CN": "g",
        "W_CN":    "w",
        "L_CN":    "l",
        "SV_CN":   "sv",
        "HOLD_CN": "hold",
        "KK_CN":   "so",
        "BB_CN":   "bb",
    },
}

# ── robots.txt ────────────────────────────────────────────────────────────────

_rp: RobotFileParser | None = None


def _robot_parser() -> RobotFileParser:
    global _rp
    if _rp is None:
        rp = RobotFileParser()
        rp.set_url(f"{_KBO_BASE}/robots.txt")
        try:
            rp.read()
        except Exception as e:
            logger.warning(f"robots.txt 읽기 실패 (허용으로 처리): {e}")
        _rp = rp
    return _rp


def _can_fetch(url: str) -> bool:
    return _robot_parser().can_fetch(settings.crawl_user_agent, url)


# ── Playwright 수집 ───────────────────────────────────────────────────────────

def _fetch_lotte_stats(page: Page, url: str) -> str | None:
    """
    Playwright page로 KBO URL을 열고 팀 드롭다운에서 롯데(LT)를 선택한 뒤
    테이블이 렌더링된 HTML을 반환한다.
    """
    if not _can_fetch(url):
        logger.warning(f"robots.txt 금지: {url}")
        return None

    try:
        page.goto(url, wait_until="networkidle", timeout=_NAV_TIMEOUT)
        page.select_option('select[name*="ddlTeam"]', _LOTTE_CODE)
        page.wait_for_load_state("networkidle", timeout=_NAV_TIMEOUT)
        page.wait_for_selector("table tbody", timeout=_SEL_TIMEOUT)
        return page.content()
    except Exception as e:
        logger.error(f"수집 실패 ({url}): {e}")
        return None


# ── 파싱 ─────────────────────────────────────────────────────────────────────

def _safe_float(text: str) -> float | None:
    text = text.strip()
    if text in ("", "-", "."):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_table(html: str, stat_map: dict[str, str]) -> list[dict]:
    """
    KBO 선수 기록 테이블 파싱.

    선수명 셀(<td> 인덱스 1, <a> 태그 포함)과 팀명 셀(인덱스 2)은
    data-id 없이 위치 기반으로 추출.
    나머지 스탯은 data-id 기반으로 추출.
    """
    soup = BeautifulSoup(html, "lxml")
    tbody = soup.select_one("table tbody")
    if not tbody:
        logger.warning("테이블 tbody 없음")
        return []

    rows: list[dict] = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        if not tds[0].get_text(strip=True).isdigit():
            continue

        a_tag = tds[1].find("a")
        if not a_tag:
            continue
        name = a_tag.get_text(strip=True)

        kbo_id = ""
        m = re.search(r"playerId=(\d+)", a_tag.get("href", ""))
        if m:
            kbo_id = m.group(1)

        team = tds[2].get_text(strip=True)
        if team != "롯데":
            continue

        stats: dict = {"name": name, "kbo_player_id": kbo_id}
        for td in tds:
            data_id = td.get("data-id", "")
            if data_id in stat_map:
                stats[stat_map[data_id]] = _safe_float(td.get_text(strip=True))

        rows.append(stats)

    return rows


# ── DB 헬퍼 ──────────────────────────────────────────────────────────────────

def _load_player_map() -> dict[str, int]:
    """players 테이블에서 {이름: player_id} 매핑을 한 번에 로드."""
    result = supabase.table("players").select("id, name, name_variants").execute()
    name_map: dict[str, int] = {}
    for row in result.data:
        name_map[row["name"]] = row["id"]
        for variant in (row.get("name_variants") or []):
            name_map[variant] = row["id"]
    return name_map


# ── 선수 명단 ─────────────────────────────────────────────────────────────────

def _try_select_team(page, url: str) -> str | None:
    """
    url을 열고 팀 드롭다운에서 롯데를 선택한 뒤 HTML을 반환한다.
    셀렉터를 순서대로 시도하여 처음 성공한 것을 사용한다.
    모든 셀렉터 실패 시 None 반환.
    """
    if not _can_fetch(url):
        logger.warning(f"robots.txt 금지: {url}")
        return None
    try:
        page.goto(url, wait_until="networkidle", timeout=_NAV_TIMEOUT)
    except Exception as e:
        logger.error(f"페이지 이동 실패 ({url}): {e}")
        return None

    for selector in _TEAM_SELECTORS:
        try:
            page.select_option(selector, _LOTTE_CODE)
            page.wait_for_load_state("networkidle", timeout=_NAV_TIMEOUT)
            page.wait_for_selector("table tbody", timeout=_SEL_TIMEOUT)
            logger.debug(f"셀렉터 성공: {selector}  url={url}")
            return page.content()
        except Exception:
            continue

    logger.warning(f"팀 드롭다운 셀렉터 모두 실패: {url}")
    return None


def _parse_names_only(html: str) -> list[str]:
    """playerId 링크를 가진 <a> 태그에서 선수명만 추출한다."""
    soup = BeautifulSoup(html, "lxml")
    names: list[str] = []
    for a in soup.select("table tbody a[href*='playerId']"):
        name = a.get_text(strip=True)
        if name:
            names.append(name)
    return names


def _fetch_active_roster_page(page) -> list[str]:
    """
    1군 등록선수 현황 페이지에서 롯데 선수명을 파싱한다.
    후보 URL과 팀 셀렉터를 순서대로 시도하여 첫 성공 결과를 반환.
    모두 실패하면 빈 리스트 반환.
    """
    for url in _ACTIVE_ROSTER_URLS:
        html = _try_select_team(page, url)
        if html:
            names = _parse_names_only(html)
            if names:
                logger.info(f"등록선수 현황 성공: {url}  → {len(names)}명")
                return names
            logger.warning(f"등록선수 현황 파싱 결과 없음: {url}")

    logger.error("등록선수 현황 수집 전체 실패 — stats 페이지로만 보완")
    return []


def fetch_roster() -> list[str]:
    """
    KBO 사이트에서 현재 롯데 1군 엔트리 선수 이름 목록을 반환한다.
    DB 연결 불필요 — 수집·라벨링 스크립트에서 키워드 생성용으로 사용.

    수집 전략:
      1순위: 등록선수 현황 페이지 (_ACTIVE_ROSTER_URLS) — 미출장 선수 포함
      2순위: stats 페이지 6개 (_URLS + _SUPPLEMENT_URLS) — 등록 페이지 실패 보완
    """
    names: set[str] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=settings.crawl_user_agent)

        # 1순위: 등록선수 현황
        roster_names = _fetch_active_roster_page(page)
        names.update(roster_names)

        # 2순위: stats 페이지 전체 (기존 3개 + 보충 3개)
        all_stat_urls = list(_URLS.values()) + _SUPPLEMENT_URLS
        stat_count_before = len(names)
        for url in all_stat_urls:
            html = _try_select_team(page, url)
            if html:
                for name in _parse_names_only(html):
                    names.add(name)

        browser.close()

    stat_added = len(names) - len(roster_names)
    logger.info(
        f"KBO 엔트리 수집 완료: 총 {len(names)}명 "
        f"(등록 현황 {len(roster_names)}명 + stats 보완 {stat_added}명)"
    )
    return sorted(names)


# ── 메인 ─────────────────────────────────────────────────────────────────────

def run(target_date: date | None = None) -> dict:
    today = target_date or date.today()
    logger.info(f"KBO 기록 수집 시작: {today}")

    player_map = _load_player_map()
    merged: dict[str, dict] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=settings.crawl_user_agent)

        for page_key, url in _URLS.items():
            html = _fetch_lotte_stats(page, url)
            if not html:
                continue
            rows = _parse_table(html, _STAT_MAP[page_key])
            logger.info(f"{page_key}: {len(rows)}명 파싱")
            for r in rows:
                entry = merged.setdefault(r["name"], {"kbo_player_id": r.get("kbo_player_id", "")})
                entry.update(r)

        browser.close()

    upsert_rows: list[dict] = []
    unmatched: list[str] = []

    for name, stats in merged.items():
        player_id = player_map.get(name)
        if not player_id:
            unmatched.append(name)
            continue

        raw = {k: v for k, v in stats.items() if k != "name"}
        upsert_rows.append({
            "player_id": player_id,
            "date":      today.isoformat(),
            "avg":       stats.get("avg"),
            "ops":       stats.get("ops"),
            "era":       stats.get("era"),
            "raw_stats": raw,
        })

    if upsert_rows:
        supabase.table("player_stats_daily").upsert(
            upsert_rows, on_conflict="player_id,date"
        ).execute()

    if unmatched:
        logger.warning(f"players 테이블 미매칭: {unmatched}")

    result = {
        "saved":     len(upsert_rows),
        "unmatched": len(unmatched),
        "date":      today.isoformat(),
    }
    logger.info(f"KBO 기록 수집 완료: {result}")
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
