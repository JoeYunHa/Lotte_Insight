"""Collect player-focused news data for labeling.

모드:
  기본: 롯데 선수별 뉴스 수집 → labeled_players.csv (is_lotte_related=true)
  --hard-negative: 타팀 선수/경기 기사 중 롯데 언급 케이스 수집
                   → labeled_players.csv (is_lotte_related=false)
                   제목 기준으로만 롯데 주체 여부 판단 (스니펫 "롯데 자이언츠" 허용)
"""

import argparse
import sys

from collect.collect_lotte_unrelated import (
    LOTTE_OPPONENT_KEYWORDS,
    _LOTTE_MAIN_SUBJECT_IN_TITLE,
    _title_starts_with_lotte_giants,
)
from collect.collect_utils import (
    BASEBALL_KEYWORDS,
    CHEERLEADER_KEYWORDS,
    FULL_KBO_TEAM_NAMES,
    LOTTE_BIZ_KEYWORDS,
    NON_BASEBALL_KEYWORDS,
    STRICT_BASEBALL_KEYWORDS,
    auto_label,
    build_days_cutoff,
    collect_news_by_keywords,
    is_mlb_giants_article,
    print_stats,
    write_csv,
)


def _has_strict_baseball_signal(title: str, snippet: str) -> bool:
    """중의어 없는 야구 키워드 또는 KBO 팀 정식·별명이 있으면 True."""
    text = (title + " " + snippet).lower()
    return (
        any(kw in text for kw in STRICT_BASEBALL_KEYWORDS)
        or any(tm in text for tm in FULL_KBO_TEAM_NAMES)
    )


def _has_lotte_biz_signal(title: str, snippet: str) -> bool:
    """롯데 그룹사 키워드(야구 무관) 언급이 있으면 True."""
    text = title + " " + snippet
    return any(b in text for b in LOTTE_BIZ_KEYWORDS)
from settings import LABELED_PLAYERS_CSV, NAVER_DISPLAY_LIMIT, REPO_ROOT, TEAM_ALIASES, TEAM_NAME_KO

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_PHOTO_PREFIXES = ("[사진]", "[포토]")
_DEFAULT_HARD_NEGATIVE_TARGET = 200


def _get_roster(player_filter: str | None) -> list[str]:
    try:
        from backend.batch.kbo_crawler import fetch_roster

        roster = fetch_roster()
        print(f"  KBO 로스터 {len(roster)}명 수집 완료")
    except Exception as exc:
        print(f"  [오류] KBO 로스터 수집 실패: {exc}")
        sys.exit(1)

    if player_filter:
        roster = [player for player in roster if player == player_filter]
        if not roster:
            print(f"  [오류] '{player_filter}' 선수를 로스터에서 찾을 수 없습니다.")
            sys.exit(1)

    return roster


def collect_by_player(roster: list[str], days_cutoff: str | None, per_keyword: int = NAVER_DISPLAY_LIMIT) -> list[dict]:
    def enrich_row(keyword: str, _row: dict) -> dict:
        return {"_search_player": keyword.removeprefix(f"{TEAM_NAME_KO} ")}

    keywords = [f"{TEAM_NAME_KO} {player}" for player in roster]
    return collect_news_by_keywords(
        keywords,
        days_cutoff=days_cutoff,
        per_keyword_limit=per_keyword,
        per_keyword_dedupe=True,
        row_enricher=enrich_row,
        display=NAVER_DISPLAY_LIMIT,
    )


def _assign_query_player(rows: list[dict]) -> list[dict]:
    """Move _search_player to query_player audit field; keep it out of detected_players."""
    for row in rows:
        row["query_player"] = row.get("_search_player", "")
    return rows


def _filter_photo_captions(rows: list[dict]) -> list[dict]:
    """Exclude photo/caption/cheerleader rows — they carry no labelable training signal."""
    before = len(rows)
    filtered = [
        row for row in rows
        if not row.get("title", "").startswith(_PHOTO_PREFIXES)
        and not any(kw in row.get("title", "") for kw in CHEERLEADER_KEYWORDS)
    ]
    removed = before - len(filtered)
    if removed:
        print(f"      [포토/사진/치어리더 제외] {removed}건 제거 -> {len(filtered)}건")
    return filtered


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in keywords)


def _filter_baseball_context(rows: list[dict]) -> list[dict]:
    """Reject articles with no baseball signal — catches off-topic name collisions."""
    before = len(rows)
    filtered = [
        row
        for row in rows
        if not (
            _has_any(f"{row.get('title', '')} {row.get('description_snippet', '')}", NON_BASEBALL_KEYWORDS)
            and not _has_any(f"{row.get('title', '')} {row.get('description_snippet', '')}", BASEBALL_KEYWORDS)
        )
    ]
    removed = before - len(filtered)
    if removed:
        print(f"      [비야구 문맥 제외] {removed}건 제거 -> {len(filtered)}건")
    return filtered


def _validate_before_write(rows: list[dict]) -> list[dict]:
    """Final gate: reject non-baseball rows; warn on ghost detected_players."""
    valid: list[dict] = []
    rejected = 0
    ghost_players = 0
    for row in rows:
        text = f"{row.get('title', '')} {row.get('description_snippet', '')}"
        if _has_any(text, NON_BASEBALL_KEYWORDS) and not _has_any(text, BASEBALL_KEYWORDS):
            rejected += 1
            continue
        players = [p for p in row.get("detected_players", "").split(";") if p.strip()]
        if players and not any(p in text for p in players):
            ghost_players += 1
        valid.append(row)
    if rejected:
        print(f"      [검증] 비야구 기사 {rejected}건 제거")
    if ghost_players:
        print(f"      [경고] detected_players가 본문에 없는 행: {ghost_players}건 (수동 검토 권장)")
    return valid


def _filter_hard_negative_rows(rows: list[dict]) -> tuple[list[dict], int]:
    """타팀 주체이면서 롯데가 언급된 hard negative 추출 (players CSV 전용).

    조건:
      - 포토/사진/치어리더 기사 제외
      - 제목에 롯데 관련 지시어 없음 (타팀이 기사의 주인공)
      - 제목이 "롯데 [비-그룹사]"로 시작하지 않음 ("롯데 김태형" 등 오분류 방지)
      - title 또는 snippet 어딘가에 "롯데"/"자이언츠" 언급 있음
      - 중의어 없는 야구 키워드 OR KBO 팀 정식명 OR 롯데 그룹사 키워드가
        있어야 함 — 금융·IT 기사가 "삼성전자", "롯데마트" snippet으로 슬립스루되는
        것을 막기 위해 엄격한 스포츠 맥락 또는 롯데 브랜드 구분 학습 근거 필요
    """
    kept: list[dict] = []
    removed = 0
    for row in rows:
        title = row.get("title", "")
        snippet = row.get("description_snippet", "")
        full_text = f"{title} {snippet}"

        if title.startswith(_PHOTO_PREFIXES):
            removed += 1
            continue
        if any(kw in title for kw in CHEERLEADER_KEYWORDS):
            removed += 1
            continue
        if any(kw in title for kw in _LOTTE_MAIN_SUBJECT_IN_TITLE):
            removed += 1
            continue
        if _title_starts_with_lotte_giants(title):
            removed += 1
            continue
        if not any(kw in full_text for kw in ("롯데", "자이언츠", "사직")):
            removed += 1
            continue
        # 야구 맥락 또는 롯데 그룹사 언급이 없으면 유의미한 False 샘플이 아님
        if not _has_strict_baseball_signal(title, snippet) and not _has_lotte_biz_signal(title, snippet):
            removed += 1
            continue
        kept.append(row)
    return kept, removed


def _force_false_player_label(rows: list[dict]) -> list[dict]:
    """hard negative 행의 is_lotte_related를 false로 강제."""
    for row in rows:
        row["is_lotte_related"] = "false"
        row["query_player"] = ""
        if not row.get("primary_label"):
            row["primary_label"] = "ETC"
        row["confidence_score"] = "1.0"
        row["confidence_note"] = "hard_negative_player_context"
    return rows


def collect_hard_negatives(
    days_cutoff: str | None,
    per_keyword: int,
    target: int,
    existing_titles: set[str],
) -> list[dict]:
    """LOTTE_OPPONENT_KEYWORDS로 타팀 vs 롯데 기사를 수집한 뒤 hard negative 필터 적용."""
    print(f"  키워드 수: {len(LOTTE_OPPONENT_KEYWORDS)}  per-keyword: {per_keyword}  target: {target}")
    rows = collect_news_by_keywords(
        LOTTE_OPPONENT_KEYWORDS,
        days_cutoff=days_cutoff,
        target_count=target * 4,
        per_keyword_limit=per_keyword,
        existing_titles=existing_titles,
    )
    print(f"  수집 완료: {len(rows)}건")

    rows, removed = _filter_hard_negative_rows(rows)
    print(f"  hard negative 필터 (제목 기준) 제거: {removed}건  남은 행: {len(rows)}건")

    rows = rows[:target]
    print(f"  target {target}건으로 자름: {len(rows)}건")
    return rows


def _filter_lotte_related(rows: list[dict], labeled: bool) -> list[dict]:
    before = len(rows)
    if labeled:
        filtered = [row for row in rows if str(row.get("is_lotte_related", "true")).lower() == "true"]
        method = "GPT is_lotte_related"
    else:
        filtered = [
            row
            for row in rows
            if any(alias in f"{row.get('title', '')} {row.get('description_snippet', '')}" for alias in TEAM_ALIASES)
            and not is_mlb_giants_article(row)
        ]
        method = "키워드"

    removed = before - len(filtered)
    print(f"      [{method}] {removed}건 제외 -> {len(filtered)}건")
    return filtered


def main():
    parser = argparse.ArgumentParser(description="선수 단위 뉴스 수집 + GPT 라벨링")
    parser.add_argument("--days", type=int, default=None, help="최근 N일 이내 기사만")
    parser.add_argument("--no-label", action="store_true", help="라벨링 건너뜀")
    parser.add_argument("--overwrite", action="store_true", help="CSV 초기화")
    parser.add_argument("--player", type=str, default=None, help="특정 선수만 수집")
    parser.add_argument(
        "--per-keyword",
        type=int,
        default=NAVER_DISPLAY_LIMIT,
        help=f"선수당 최대 수집 건수 (기본={NAVER_DISPLAY_LIMIT}, 최대 1000, 100 초과 시 페이지네이션)",
    )
    parser.add_argument(
        "--hard-negative",
        action="store_true",
        help=(
            "타팀 선수/경기 기사 중 롯데가 언급된 hard negative 수집. "
            "is_lotte_related=false로 labeled_players.csv에 저장. "
            f"(기본 target: {_DEFAULT_HARD_NEGATIVE_TARGET}건)"
        ),
    )
    parser.add_argument(
        "--target",
        type=int,
        default=_DEFAULT_HARD_NEGATIVE_TARGET,
        help=f"--hard-negative 모드에서 수집할 목표 건수 (기본: {_DEFAULT_HARD_NEGATIVE_TARGET})",
    )
    args = parser.parse_args()

    cutoff = build_days_cutoff(args.days)
    per_keyword = max(1, min(args.per_keyword, 1000))

    # ── hard negative 모드 ────────────────────────────────────────────────────
    if args.hard_negative:
        from collect.collect_utils import load_existing_titles

        print("=== hard negative 수집 모드 (labeled_players.csv) ===")
        print(f"    타깃: {args.target}건  per-keyword: {per_keyword}\n")

        existing_titles = load_existing_titles(LABELED_PLAYERS_CSV)
        print(f"[1/3] 기존 CSV 제목 수: {len(existing_titles)}")

        print("\n[2/3] 타팀 vs 롯데 기사 수집 및 필터링")
        rows = collect_hard_negatives(
            days_cutoff=cutoff,
            per_keyword=per_keyword,
            target=args.target,
            existing_titles=existing_titles,
        )

        if not rows:
            print("수집된 기사 없음 — 종료")
            return

        rows = _force_false_player_label(rows)

        print(f"\n[3/3] CSV 저장: {LABELED_PLAYERS_CSV}")
        saved = write_csv(rows, LABELED_PLAYERS_CSV, append=True)
        print(f"      {saved}건 저장 완료 (is_lotte_related=false)")
        return

    # ── 기본 모드: 롯데 선수 수집 ─────────────────────────────────────────────
    print("[1/6] KBO 로스터 수집 (Playwright) ...")
    roster = _get_roster(args.player)
    print(f"      선수 {len(roster)}명: {', '.join(roster)}")
    print(f"      (선수당 최대 {per_keyword}건)\n")

    print("[2/6] 선수별 뉴스 수집")
    rows = collect_by_player(roster, cutoff, per_keyword=per_keyword)
    print(f"      수집 완료: {len(rows)}건\n")

    print("[3/6] 전처리 필터링")
    rows = _assign_query_player(rows)
    rows = _filter_photo_captions(rows)
    rows = _filter_baseball_context(rows)
    print(f"      전처리 후: {len(rows)}건\n")

    if not args.no_label:
        print("[4/6] GPT 자동 라벨링")

        def extra_ctx(row: dict) -> str:
            return f"검색 선수: {row['query_player']} ({TEAM_NAME_KO} 자이언츠 소속)"

        def ensure_players(row: dict) -> list[str]:
            # Scan against full roster so all mentioned players are detected,
            # not just the search keyword that found this article.
            return roster

        rows = auto_label(rows, extra_context_fn=extra_ctx, ensure_players_fn=ensure_players)
        print_stats(rows)
    else:
        print("[4/6] 라벨링 건너뜀 (--no-label)")
        for row in rows:
            text = f"{row.get('title', '')} {row.get('description_snippet', '')}"
            row["detected_players"] = ";".join(p for p in roster if p in text)
            row["is_lotte_related"] = "true"

    print("\n[5/6] 관련성 보정 및 검증")
    rows = _filter_lotte_related(rows, labeled=not args.no_label)
    rows = _validate_before_write(rows)

    print(f"\n[6/6] CSV 저장: {LABELED_PLAYERS_CSV}")
    saved = write_csv(rows, LABELED_PLAYERS_CSV, append=not args.overwrite)
    print(f"      {saved}건 저장 완료")

    if not args.no_label:
        low_confidence = [
            row for row in rows if row.get("confidence_score") and float(row["confidence_score"]) < 0.7
        ]
        if low_confidence:
            print(f"\n검토 권장: confidence < 0.7 항목 {len(low_confidence)}건")


if __name__ == "__main__":
    main()