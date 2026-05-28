"""
롯데 자이언츠 경기 결과 + 키플레이어 + 세부 리뷰 수집기.

출처:
  - 네이버 스포츠 Calendar API  → game_id 목록, 홈/원정 팀
  - 네이버 스포츠 Record API     → 최종 스코어
  - KBO 공식 BoxScore ASMX      → tableEtc (결승타·홈런·실책 등)
  - KBO 공식 KeyPlayer ASMX     → WPA 기준 키플레이어

사용법:
    python collect_game_results.py                        # 현재 연도 전체
    python collect_game_results.py --year 2026 --month 4
    python collect_game_results.py --since 2026-03-01     # 해당 날짜 이후 전체

저장 위치: training/data/game_results.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import httpx

from settings import GAME_RESULTS_CSV

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

LOTTE_CODE = "LT"

TEAM_NAME_MAP: dict[str, str] = {
    "HB": "KIA", "SS": "삼성", "LG": "LG", "OB": "두산",
    "KT": "KT",  "SK": "SSG", "LT": "롯데", "HH": "한화",
    "NC": "NC",  "WO": "키움",
}

_GAME_FLAG_TO_SERIES_ID: dict[str, int] = {"0": 0, "1": 1}

NAVER_CALENDAR_URL = "https://api-gw.sports.naver.com/schedule/calendar"
NAVER_RECORD_URL   = "https://api-gw.sports.naver.com/schedule/games"

KBO_BOXSCORE_URL   = "https://www.koreabaseball.com/ws/Schedule.asmx/GetBoxScoreScroll"
KBO_KEYHITTER_URL  = "https://www.koreabaseball.com/ws/Schedule.asmx/GetKeyPlayerHitter"
KBO_KEYPITCHER_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetKeyPlayerPitcher"

NAVER_HEADERS = {
    "Origin":  "https://m.sports.naver.com",
    "Referer": "https://m.sports.naver.com/",
    "User-Agent": "Mozilla/5.0",
}
KBO_HEADERS = {
    "Content-Type":    "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer":         "https://www.koreabaseball.com/",
    "Origin":          "https://www.koreabaseball.com",
    "X-Requested-With": "XMLHttpRequest",
}

DELAY_NAVER = 0.3
DELAY_KBO   = 0.5

CSV_HEADERS = [
    "game_date",           # YYYY-MM-DD
    "game_id",             # 네이버 game_id
    "home_team",           # 홈팀 코드
    "away_team",           # 원정팀 코드
    "lotte_home_away",     # H / A
    "opponent",            # 상대팀 코드
    "home_score",
    "away_score",
    "lotte_score",
    "opponent_score",
    "result",              # W / L / D / postponed
    "series_id",           # 0=정규, 1=시범
    "extra_innings",       # 연장 이닝 수 (없으면 "")
    "winning_rbi_player",  # 결승타 선수
    "winning_rbi_inning",  # 결승타 이닝
    "winning_rbi_detail",  # 결승타 상세
    "home_runs",           # "선수명N호;..." 세미콜론 구분
    "key_hitters",         # WPA 상위 타자 "선수명(팀);..." 세미콜론 구분
    "key_pitchers",        # WPA 상위 투수 "선수명(팀);..." 세미콜론 구분
    "review_raw",          # 특기사항 원본 "카테고리:내용|..." 파이프 구분
]

# ---------------------------------------------------------------------------
# 파서 (kbo_review_parser / kbo_keyplayer_parser 핵심 로직 인라인)
# ---------------------------------------------------------------------------

_HR_ENTRY_RE  = re.compile(r"(\S+?)(\d+호(?:\d+호)*)\(([^)]+)\)")
_HR_EVENT_RE  = re.compile(r"^(\d+)회(\d+)점$")
_WINNING_RE   = re.compile(r"^(\S+?)\((.+)\)$")
_INNING_RE    = re.compile(r"(\d+)회")
_RECORD_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)

_UMPIRE_CATS: frozenset[str] = frozenset({
    "심판", "주심", "1루심", "2루심", "3루심",
    "좌선심", "우선심", "외야심", "좌야선심", "우야선심",
})


def _is_umpire(category: str) -> bool:
    return category in _UMPIRE_CATS or category.endswith("심")


def _parse_hr_text(text: str) -> list[str]:
    """홈런 텍스트 → "선수명N호" 문자열 목록."""
    result: list[str] = []
    for m in _HR_ENTRY_RE.finditer(text):
        player   = m.group(1)
        hr_nos   = re.findall(r"\d+", m.group(2))
        for no in hr_nos:
            result.append(f"{player}{no}호")
    return result


def _parse_winning_rbi(text: str) -> tuple[str, str, str]:
    """결승타 텍스트 → (player, inning, detail)."""
    m = _WINNING_RE.match(text.strip())
    if not m:
        return "", "", text.strip()
    player = m.group(1)
    detail = m.group(2)
    inn_m  = _INNING_RE.search(detail)
    inning = inn_m.group(1) if inn_m else ""
    return player, inning, detail


def parse_table_etc(raw: str | dict) -> dict:
    """
    GetBoxScoreScroll tableEtc → {카테고리: 파싱 결과}.
    result["결승타"] = (player, inning, detail)
    result["홈런"]   = ["선수명N호", ...]
    result["_raw"]   = {카테고리: 원본텍스트}  (심판 제외)
    """
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    else:
        data = raw

    result: dict = {"_raw": {}}
    for row_obj in data.get("rows", []):
        cells = row_obj.get("row", [])
        if len(cells) < 2:
            continue
        key   = (cells[0].get("Text") or "").strip()
        value = (cells[1].get("Text") or "").strip()
        if not key or not value:
            continue
        if _is_umpire(key):
            continue

        result["_raw"][key] = value

        if key == "홈런":
            result["홈런"] = _parse_hr_text(value)
        elif key == "결승타":
            result["결승타"] = _parse_winning_rbi(value)
        else:
            result[key] = value

    return result


def parse_keyplayer_top(data: dict, n: int = 3) -> list[str]:
    """
    GetKeyPlayerHitter/Pitcher 응답 → 상위 n명 "선수명(팀)" 목록.
    code=="100" 아니면 빈 리스트.
    """
    if data.get("code") != "100":
        return []
    result: list[str] = []
    for rec in data.get("record", [])[:n]:
        name = rec.get("P_NM", "")
        team = TEAM_NAME_MAP.get(rec.get("T_ID", ""), rec.get("T_ID", ""))
        if name:
            result.append(f"{name}({team})")
    return result


# ---------------------------------------------------------------------------
# 네이버 Calendar API → 롯데 경기 game_id 목록
# ---------------------------------------------------------------------------

async def fetch_lotte_game_ids(
    client: httpx.AsyncClient,
    year: int,
    month: int,
) -> list[dict]:
    """해당 년월의 롯데 완료 경기 목록 반환."""
    try:
        r = await client.get(
            NAVER_CALENDAR_URL,
            params={
                "upperCategoryId": "kbaseball",
                "categoryIds": ",kbo,kbs,kbaseballetc",
                "date": f"{year}-{month:02d}-01",
            },
            timeout=15,
        )
        r.raise_for_status()
    except Exception as exc:
        print(f"  [ERROR] Calendar API 실패 ({year}-{month:02d}): {exc}")
        return []

    games: list[dict] = []
    for day in r.json().get("result", {}).get("dates", []):
        for gi in day.get("gameInfos") or []:
            game_id = gi.get("gameId", "")
            if not game_id.startswith(str(year)) or len(game_id) > 20:
                continue
            home = gi.get("homeTeamCode", "")
            away = gi.get("awayTeamCode", "")
            if len(home) != 2 or len(away) != 2:
                continue
            if LOTTE_CODE not in (home, away):
                continue
            if gi.get("statusCode") != "RESULT":
                continue
            series_id = _GAME_FLAG_TO_SERIES_ID.get(str(gi.get("gameFlag", "0")), 0)
            games.append({
                "game_id":   game_id,
                "game_date": day["ymd"],
                "season":    year,
                "series_id": series_id,
                "home_team": home,
                "away_team": away,
            })

    await asyncio.sleep(DELAY_NAVER)
    return games


# ---------------------------------------------------------------------------
# 네이버 Record API → 스코어
# ---------------------------------------------------------------------------

async def fetch_scores(
    client: httpx.AsyncClient,
    game_id: str,
) -> tuple[int | None, int | None]:
    """(home_score, away_score) 반환. 실패 시 (None, None)."""
    try:
        r = await client.get(f"{NAVER_RECORD_URL}/{game_id}/record", timeout=10)
        if r.status_code != 200:
            return None, None
        rd = r.json().get("result", {}).get("recordData", {})

        # 경로 1: scoreBoard.rheb.home/away.r
        rheb = rd.get("scoreBoard", {}).get("rheb", {})
        h = rheb.get("home", {})
        a = rheb.get("away", {})
        if h.get("r") is not None and a.get("r") is not None:
            return int(h["r"]), int(a["r"])

        # 경로 2: battersBoxscore homeTotal/awayTotal.run
        bb = rd.get("battersBoxscore", {})
        ht = bb.get("homeTotal", {})
        at = bb.get("awayTotal", {})
        if ht.get("run") is not None and at.get("run") is not None:
            return int(ht["run"]), int(at["run"])

    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# KBO ASMX → BoxScore (tableEtc)
# ---------------------------------------------------------------------------

def _to_kbo_id(naver_game_id: str) -> str:
    """네이버 game_id 마지막 4자리(연도) 제거 → KBO 공식 game_id."""
    return naver_game_id[:-4]


async def fetch_boxscore_review(
    client: httpx.AsyncClient,
    game_id: str,
    season: int,
    series_id: int,
) -> dict:
    """tableEtc 파싱 결과 반환. 실패 시 빈 dict."""
    try:
        r = await client.post(
            KBO_BOXSCORE_URL,
            data={
                "leId":     1,
                "srId":     series_id,
                "seasonId": season,
                "gameId":   _to_kbo_id(game_id),
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "100":
            return {}
        return parse_table_etc(data.get("tableEtc", ""))
    except Exception as exc:
        print(f"    [WARN] BoxScore 실패 {game_id}: {exc}")
        return {}


# ---------------------------------------------------------------------------
# KBO ASMX → KeyPlayer (WPA 기준 상위 3명)
# ---------------------------------------------------------------------------

async def fetch_key_players(
    client: httpx.AsyncClient,
    game_id: str,
    series_id: int,
) -> tuple[list[str], list[str]]:
    """(key_hitters, key_pitchers) WPA 기준 상위 3명씩."""
    kbo_id = _to_kbo_id(game_id)
    base_data = {
        "leId":    1,
        "srId":    series_id,
        "gameId":  kbo_id,
        "groupSc": "GAME_WPA_RT",
        "sort":    "DESC",
    }

    hitters: list[str] = []
    pitchers: list[str] = []

    try:
        r = await client.post(KBO_KEYHITTER_URL, data=base_data, timeout=10)
        r.raise_for_status()
        hitters = parse_keyplayer_top(r.json())
        await asyncio.sleep(DELAY_KBO)
    except Exception as exc:
        print(f"    [WARN] KeyHitter 실패 {game_id}: {exc}")

    try:
        r = await client.post(KBO_KEYPITCHER_URL, data=base_data, timeout=10)
        r.raise_for_status()
        pitchers = parse_keyplayer_top(r.json())
        await asyncio.sleep(DELAY_KBO)
    except Exception as exc:
        print(f"    [WARN] KeyPitcher 실패 {game_id}: {exc}")

    return hitters, pitchers


# ---------------------------------------------------------------------------
# 경기 결과 row 조립
# ---------------------------------------------------------------------------

def _result(lotte: int | None, opp: int | None) -> str:
    if lotte is None or opp is None:
        return "unknown"
    if lotte > opp:
        return "W"
    if lotte < opp:
        return "L"
    return "D"


def _review_raw_str(review: dict) -> str:
    """특기사항 원본 텍스트 → "카테고리:내용|..." 문자열."""
    parts: list[str] = []
    for k, v in review.get("_raw", {}).items():
        parts.append(f"{k}:{v}")
    return "|".join(parts)


async def collect_game(
    naver_client: httpx.AsyncClient,
    kbo_client:   httpx.AsyncClient,
    game: dict,
) -> dict:
    game_id   = game["game_id"]
    game_date = game["game_date"]
    season    = game["season"]
    series_id = game["series_id"]
    home      = game["home_team"]
    away      = game["away_team"]

    is_home   = home == LOTTE_CODE
    opponent  = away if is_home else home

    # ── 스코어 ────────────────────────────────────────────────────────────────
    home_score, away_score = await fetch_scores(naver_client, game_id)
    await asyncio.sleep(DELAY_NAVER)

    lotte_score = home_score if is_home else away_score
    opp_score   = away_score if is_home else home_score

    # ── BoxScore 리뷰 ─────────────────────────────────────────────────────────
    review = await fetch_boxscore_review(kbo_client, game_id, season, series_id)
    await asyncio.sleep(DELAY_KBO)

    winning = review.get("결승타", ("", "", ""))
    home_runs = review.get("홈런", [])

    # 연장 이닝: review raw 내 "연장" 키 탐색
    extra = ""
    raw_map = review.get("_raw", {})
    for k in raw_map:
        m = re.search(r"연장\s*(\d+)\s*회", k + raw_map[k])
        if m:
            extra = m.group(1)
            break

    # ── 키플레이어 ────────────────────────────────────────────────────────────
    key_hitters, key_pitchers = await fetch_key_players(kbo_client, game_id, series_id)

    return {
        "game_date":          game_date,
        "game_id":            game_id,
        "home_team":          home,
        "away_team":          away,
        "lotte_home_away":    "H" if is_home else "A",
        "opponent":           opponent,
        "home_score":         "" if home_score is None else home_score,
        "away_score":         "" if away_score is None else away_score,
        "lotte_score":        "" if lotte_score is None else lotte_score,
        "opponent_score":     "" if opp_score   is None else opp_score,
        "result":             _result(lotte_score, opp_score),
        "series_id":          series_id,
        "extra_innings":      extra,
        "winning_rbi_player": winning[0] if winning else "",
        "winning_rbi_inning": winning[1] if winning else "",
        "winning_rbi_detail": winning[2] if winning else "",
        "home_runs":          ";".join(home_runs),
        "key_hitters":        ";".join(key_hitters),
        "key_pitchers":       ";".join(key_pitchers),
        "review_raw":         _review_raw_str(review),
    }


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["game_id"]: row for row in csv.DictReader(f)}


@lru_cache(maxsize=1)
def _games_by_date() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in load_existing(GAME_RESULTS_CSV).values():
        game_date = row.get("game_date", "")
        if not game_date:
            continue
        grouped.setdefault(game_date, []).append(row)
    return grouped


def save_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(rows, key=lambda r: (r["game_date"], r["game_id"]))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(sorted_rows)


# ---------------------------------------------------------------------------
# GPT 프롬프트용 컨텍스트 문자열 생성
# ---------------------------------------------------------------------------

def format_game_context(game: dict | None) -> str:
    """
    기사 날짜·시각 기준 관련 경기 결과를 GPT 프롬프트용 문자열로 반환.
    game이 None이거나 result가 'unknown'이면 "해당 날짜 경기 없음" 반환.
    """
    if not game or game.get("result") in ("unknown", "", None):
        return "해당 날짜 경기 없음"

    result_ko = {"W": "승", "L": "패", "D": "무", "postponed": "취소"}.get(
        game["result"], game["result"]
    )
    ha_ko  = "홈" if game["lotte_home_away"] == "H" else "원정"
    opp_ko = TEAM_NAME_MAP.get(game["opponent"], game["opponent"])
    extra  = f" (연장 {game['extra_innings']}회)" if game.get("extra_innings") else ""
    score  = ""
    if str(game.get("lotte_score", "")) and str(game.get("opponent_score", "")):
        score = f" {game['lotte_score']}-{game['opponent_score']}"

    parts = [f"롯데 vs {opp_ko} ({ha_ko}){score} {result_ko}{extra}"]

    if game.get("winning_rbi_player"):
        parts.append(f"결승타: {game['winning_rbi_player']}({game.get('winning_rbi_inning','')}회)")
    if game.get("home_runs"):
        parts.append(f"홈런: {game['home_runs'].replace(';', ', ')}")
    if game.get("key_hitters"):
        parts.append(f"타자 키플레이어: {game['key_hitters'].replace(';', ', ')}")
    if game.get("key_pitchers"):
        parts.append(f"투수 키플레이어: {game['key_pitchers'].replace(';', ', ')}")

    return " | ".join(parts)


def lookup_game(target_date: date, hour: int = 12) -> dict | None:
    """
    기사 날짜·시각 기준으로 관련 경기를 반환.
    오전(hour < 15): 전날 경기 우선, 없으면 당일
    오후(hour >= 15): 당일 경기 우선, 없으면 전날
    """
    from datetime import timedelta
    games_by_date = _games_by_date()
    if not games_by_date:
        return None

    if hour < 15:
        keys = [
            (target_date - timedelta(days=1)).isoformat(),
            target_date.isoformat(),
        ]
    else:
        keys = [
            target_date.isoformat(),
            (target_date - timedelta(days=1)).isoformat(),
        ]

    for key in keys:
        for game in games_by_date.get(key, []):
            if game.get("game_date") == key and game.get("result") not in ("unknown", "", None):
                return game
    return None


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

async def collect(year: int, months: list[int]) -> None:
    existing = load_existing(GAME_RESULTS_CSV)
    all_rows = dict(existing)
    total_new = 0

    async with (
        httpx.AsyncClient(headers=NAVER_HEADERS) as naver_client,
        httpx.AsyncClient(headers=KBO_HEADERS)   as kbo_client,
    ):
        for month in sorted(set(months)):
            print(f"\n[{year}-{month:02d}] game_id 수집 중...")
            games = await fetch_lotte_game_ids(naver_client, year, month)
            new_games = [g for g in games if g["game_id"] not in all_rows]
            print(f"  완료 경기 {len(games)}건 / 신규 수집 대상 {len(new_games)}건")

            for i, game in enumerate(new_games, 1):
                gid = game["game_id"]
                print(f"  [{i:>2}/{len(new_games)}] {game['game_date']} {gid} ...", end=" ", flush=True)
                try:
                    row = await collect_game(naver_client, kbo_client, game)
                    all_rows[gid] = row
                    total_new += 1
                    result = row["result"]
                    score  = f"{row['lotte_score']}-{row['opponent_score']}"
                    print(f"{result} {score} 결승타={row['winning_rbi_player'] or '-'}")
                except Exception as exc:
                    print(f"ERROR: {exc}")

    save_csv(list(all_rows.values()), GAME_RESULTS_CSV)
    print(f"\n저장 완료: {GAME_RESULTS_CSV}")
    print(f"  총 {len(all_rows)}건 (신규 {total_new}건)")


def main() -> None:
    parser = argparse.ArgumentParser(description="롯데 자이언츠 경기 결과 수집")
    parser.add_argument("--year",  type=int, default=date.today().year)
    parser.add_argument("--month", type=int, action="append", dest="months")
    parser.add_argument("--since", type=date.fromisoformat, default=None,
                        help="YYYY-MM-DD 이후 모든 월 수집")
    args = parser.parse_args()

    year   = args.year
    months = args.months or []

    if args.since:
        year   = args.since.year
        today  = date.today()
        cur_y, cur_m = args.since.year, args.since.month
        while (cur_y, cur_m) <= (today.year, today.month):
            if cur_y == year:
                months.append(cur_m)
            cur_m += 1
            if cur_m > 12:
                cur_m = 1
                cur_y += 1

    if not months:
        months = list(range(3, date.today().month + 1))  # KBO 시즌: 3월~현재

    asyncio.run(collect(year, months))


if __name__ == "__main__":
    main()
