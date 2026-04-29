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

import requests as http
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


_REGISTER_URL = f"{_KBO_BASE}/Player/Register.aspx"

# Register.aspx POST 필드명 (진단 스크립트로 확인)
_REG_TEAM_FIELD = (
    "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$hfSearchTeam"
)
_REG_DATE_FIELD = (
    "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$hfSearchDate"
)
_REG_EVENT_TARGET = (
    "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$btnCalendarSelect"
)

# ── 선수 명단 ─────────────────────────────────────────────────────────────────


def _try_select_team(page, url: str) -> str | None:
    """
    stats 페이지(url)를 열고 SELECT 드롭다운으로 롯데(LT)를 선택한 뒤 HTML을 반환한다.
    드롭다운 선택에 실패하면 None을 반환한다. run()의 일간 기록 수집에서 사용.
    """
    if not _can_fetch(url):
        logger.warning(f"robots.txt 금지: {url}")
        return None
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT)
        page.wait_for_selector("table tbody tr", timeout=_SEL_TIMEOUT)
    except Exception as e:
        logger.error(f"페이지 이동 실패 ({url}): {e}")
        return None

    for selector in _TEAM_SELECTORS:
        try:
            page.select_option(selector, _LOTTE_CODE)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            page.wait_for_selector("table tbody tr", timeout=_SEL_TIMEOUT)
            logger.debug(f"드롭다운 성공: {selector}")
            return page.content()
        except Exception:
            continue

    logger.warning(f"팀 드롭다운 선택 실패: {url}")
    return None




def _extract_update_panel(text: str) -> str:
    """
    ASP.NET UpdatePanel AJAX 응답(파이프 구분 포맷)에서 updatePanel 섹션 HTML을 추출한다.
    일반 HTML 응답이면 그대로 반환한다.

    포맷: <length>|<type>|<id>|<content>|...
    """
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
        rtype = text[pipe1 + 1:pipe2]
        pipe3 = text.find("|", pipe2 + 1)
        if pipe3 < 0:
            break
        content_start = pipe3 + 1
        if rtype == "updatePanel":
            parts.append(text[content_start:content_start + length])
        pos = content_start + length + 1  # trailing |
    return "\n".join(parts) if parts else text


_STAFF_SECTIONS = {"감독", "코치"}


def _parse_register_names(html: str) -> list[str]:
    """
    Register.aspx HTML에서 선수 이름 목록을 추출한다.

    테이블 구조: 테이블마다 헤더 행(행0)의 두 번째 셀이 섹션명을 나타낸다.
      감독 / 코치          → 건너뜀
      투수 / 포수 / 내야수 / 외야수 → 파싱
    데이터 행의 colspan > 1 이면 빈 안내 행(당일 등록 없음 등) → 건너뜀.
    """
    soup = BeautifulSoup(html, "lxml")
    names: list[str] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        # 헤더 행으로 섹션 타입 판별
        header_cells = rows[0].find_all(["td", "th"])
        if len(header_cells) < 2:
            continue
        section = header_cells[1].get_text(strip=True)
        if section in _STAFF_SECTIONS:
            continue

        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            if int(cells[0].get("colspan", 1)) > 1:
                continue  # "당일 등록된 선수가 없습니다" 등 안내 행
            if not cells[0].get_text(strip=True).isdigit():
                continue
            a_tag = cells[1].find("a")
            name = a_tag.get_text(strip=True) if a_tag else cells[1].get_text(strip=True)
            if name:
                names.append(name)

    return names


def fetch_roster() -> list[str]:
    """
    KBO Register.aspx에 requests로 직접 POST하여 롯데 엔트리를 반환한다.
    DB 연결 불필요 — 수집·라벨링 스크립트에서 키워드 생성용으로 사용.

    fnSearchChange('LT')의 동작을 재현:
      1. GET으로 __VIEWSTATE 등 폼 토큰 획득
      2. POST: __EVENTTARGET=btnCalendarSelect, hfSearchTeam=LT
    """
    if not _can_fetch(_REGISTER_URL):
        logger.warning(f"robots.txt 금지: {_REGISTER_URL}")
        return []

    session = http.Session()
    session.headers.update({
        "User-Agent": settings.crawl_user_agent,
        "Referer": _REGISTER_URL,
    })

    try:
        # 1. 초기 GET — ViewState / EventValidation / 날짜 필드 획득
        resp = session.get(_REGISTER_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        def _hidden(name: str) -> str:
            el = soup.find("input", {"name": name})
            return el.get("value", "") if el else ""

        search_date = _hidden(_REG_DATE_FIELD) or date.today().strftime("%Y%m%d")

        # 2. POST — 롯데(LT) 팀 선택 (fnSearchChange 동작 재현)
        post_data = {
            "__VIEWSTATE":          _hidden("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": _hidden("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION":    _hidden("__EVENTVALIDATION"),
            "__EVENTTARGET":        _REG_EVENT_TARGET,
            "__EVENTARGUMENT":      "",
            _REG_TEAM_FIELD:        _LOTTE_CODE,
            _REG_DATE_FIELD:        search_date,
        }
        resp2 = session.post(_REGISTER_URL, data=post_data, timeout=30)
        resp2.raise_for_status()
        resp2.encoding = resp2.apparent_encoding

        # UpdatePanel 부분 응답이면 HTML 섹션만 추출
        html = _extract_update_panel(resp2.text)
        print(f"      응답 {len(resp2.text):,}자 (UpdatePanel: {'예' if html != resp2.text else '아니오'})")

        names = _parse_register_names(html)
        logger.info(f"KBO 엔트리 수집 완료: 총 {len(names)}명 (Register.aspx)")
        return sorted(names)

    except Exception as e:
        logger.error(f"Register.aspx 수집 실패: {e}")
        return []


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
