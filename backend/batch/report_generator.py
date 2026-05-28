"""
Generate daily team and player reports.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

from openai import OpenAI

from core.config import settings
from services import report_repository
from services.article_utils import parse_event_summary_json, select_primary_label

logger = logging.getLogger(__name__)
_openai_client: OpenAI | None = None

_LABEL_NAMES_KO: dict[str, str] = {
    "MATCH_RELATED": "경기",
    "INJURY_ROSTER": "부상·엔트리",
    "TRANSACTION_CONTRACT": "거래·계약",
    "PERFORMANCE_ANALYSIS": "성적 분석",
    "INTERVIEW": "인터뷰",
    "CLUB_OPERATION": "구단 운영",
    "ETC": "기타",
}

_TEAM_SYSTEM_PROMPT = (
    "당신은 KBO {team_name_ko} 자이언츠 전문 여론 분석가입니다. "
    "오늘 수집된 뉴스 데이터를 받아 팬이 읽기 좋은 브리핑을 작성합니다.\n\n"
    "[목표]\n"
    "제공된 기사 분류 현황, 주요 언급 선수, 핵심 이슈 요약을 근거로 "
    "팬 관점에서 오늘 롯데 여론의 핵심을 150자 이내 한국어 문단으로 작성하세요.\n\n"
    "[원칙]\n"
    "- 제공된 데이터에 없는 내용은 절대 사용하지 마세요.\n"
    "- 구체적인 이슈와 선수명을 포함하세요.\n"
    "- 단정적 예측, 추측, 부상 상태 추정은 금지합니다.\n"
    "- 불릿, 제목, 이모지 사용 금지.\n"
    "- 출력은 한 문단만 작성하세요."
)

_TEAM_REPORT_MAX_TOKENS = 250
_TEAM_EVENT_TEXT_LIMIT = 8
_PLAYER_REPORT_WORKERS = 4


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _extract_event_summary(raw_summary: str | None) -> str:
    return parse_event_summary_json(raw_summary).get("event_summary") or ""


def _summarize_label_counts(articles: list[dict]) -> dict[str, int]:
    """기사 단위 대표 라벨(최고 confidence)만 카운트 — 멀티라벨 중복 합산 방지."""
    label_counts: dict[str, int] = {}
    for article in articles:
        label = select_primary_label(article.get("article_labels") or [])
        if label:
            label_counts[label] = label_counts.get(label, 0) + 1
    return label_counts


def _summarize_player_mentions(mentions: list[dict]) -> dict[str, int]:
    player_mentions: dict[str, int] = {}
    for row in mentions:
        name = (row.get("players") or {}).get("name", "")
        if name:
            player_mentions[name] = player_mentions.get(name, 0) + 1
    return player_mentions


def _build_team_event_texts(articles: list[dict]) -> list[str]:
    """라벨별 최대 2건씩 균형 있게 뽑아 GPT 입력용 텍스트 목록을 만든다."""
    from collections import defaultdict
    buckets: dict[str, list[str]] = defaultdict(list)
    unlabeled: list[str] = []

    for article in articles:
        event_summary = _extract_event_summary(article.get("event_summary"))
        text = event_summary or article.get("title", "")
        if not text:
            continue
        labels = article.get("article_labels") or []
        label = select_primary_label(labels)
        if label:
            buckets[label].append(text)
        else:
            unlabeled.append(text)

    texts: list[str] = []
    per_label = max(1, _TEAM_EVENT_TEXT_LIMIT // max(len(buckets), 1))
    for bucket in buckets.values():
        texts.extend(bucket[:per_label])
        if len(texts) >= _TEAM_EVENT_TEXT_LIMIT:
            break
    remaining = _TEAM_EVENT_TEXT_LIMIT - len(texts)
    if remaining > 0:
        texts.extend(unlabeled[:remaining])
    return texts[:_TEAM_EVENT_TEXT_LIMIT]


def _build_team_gpt_prompt(
    article_count: int,
    label_counts: dict[str, int],
    player_mentions: dict[str, int],
    event_texts: list[str],
) -> str:
    label_summary = ", ".join(
        f"{_LABEL_NAMES_KO.get(label, label)} {count}건"
        for label, count in sorted(label_counts.items(), key=lambda x: -x[1])
        if count > 0
    ) or "없음"
    top_players = sorted(player_mentions.items(), key=lambda x: -x[1])[:5]
    player_summary = ", ".join(f"{name}({count}회)" for name, count in top_players) or "없음"
    texts_block = "\n".join(f"- {t}" for t in event_texts) or "- (이슈 요약 없음)"
    return (
        f"기사 수: {article_count}건\n"
        f"라벨 분포: {label_summary}\n"
        f"주요 언급 선수: {player_summary}\n"
        f"주요 이슈 요약:\n{texts_block}"
    )


def _generate_team_insight(user_prompt: str) -> str | None:
    try:
        response = _get_openai().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": _TEAM_SYSTEM_PROMPT.format(team_name_ko=settings.team_name_ko),
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=_TEAM_REPORT_MAX_TOKENS,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("Failed to generate team insight via GPT: %s", exc)
        return None


def _format_team_report(today: date, articles: list[dict], mentions: list[dict]) -> dict:
    label_counts = _summarize_label_counts(articles)
    player_mentions = _summarize_player_mentions(mentions)
    top_labels = [
        label
        for label, _ in sorted(label_counts.items(), key=lambda x: -x[1])[:3]
        if label_counts[label] > 0
    ]

    event_texts = _build_team_event_texts(articles)
    user_prompt = _build_team_gpt_prompt(len(articles), label_counts, player_mentions, event_texts)
    insight = _generate_team_insight(user_prompt)

    if not insight:
        # GPT 실패 시 템플릿 fallback
        label_summary = ", ".join(
            f"{_LABEL_NAMES_KO.get(l, l)} {c}건"
            for l, c in sorted(label_counts.items(), key=lambda x: -x[1])
            if c > 0
        ) or "없음"
        top_players = sorted(player_mentions.items(), key=lambda x: -x[1])[:5]
        player_summary = ", ".join(f"{name}({cnt})" for name, cnt in top_players) or "없음"
        insight = (
            f"오늘 {settings.team_name_ko} 자이언츠 관련 기사 {len(articles)}건. "
            f"분류 현황: {label_summary}. "
            f"주요 언급 선수: {player_summary}."
        )
        logger.warning("Team insight fallback to template (GPT unavailable)")

    return {
        "date": today.isoformat(),
        "issue_summary": insight,
        "article_count": len(articles),
        "top_labels": top_labels,
    }


def _build_team_report(today: date) -> dict | None:
    if report_repository.report_exists("team_daily_report", today):
        logger.info("Team report already exists, skipping: %s", today)
        return None

    articles = report_repository.fetch_articles_for_day(today)
    article_ids = [article["id"] for article in articles]
    mentions = report_repository.fetch_player_mentions(article_ids)
    return _format_team_report(today, articles, mentions)


def _collect_recent_titles(player_id: int, since: date) -> list[str]:
    article_rows = report_repository.fetch_recent_player_articles(
        player_id,
        since=since,
        limit=settings.player_report_article_limit,
    )
    results = []
    for row in article_rows:
        article = row.get("articles")
        if not article:
            continue
        summary = _extract_event_summary(article.get("event_summary"))
        results.append(summary or article["title"])
    return results


def _format_stats_snapshot(stat_snapshot: dict) -> str:
    if not stat_snapshot:
        return "기록 없음"
    return (
        f"타율 {stat_snapshot.get('avg', 'N/A')}, "
        f"OPS {stat_snapshot.get('ops', 'N/A')}, "
        f"ERA {stat_snapshot.get('era', 'N/A')}"
    )


def _build_player_prompt(player_name: str, titles: list[str], stat_snapshot: dict) -> str:
    titles_text = "\n".join(f"- {title}" for title in titles) or "관련 기사 없음"
    stats_text = _format_stats_snapshot(stat_snapshot)
    return (
        f"선수명: {player_name}\n\n"
        f"최근 기사 요약:\n{titles_text}\n\n"
        f"최근 기록: {stats_text}"
    )


def _build_player_report(player_id: int, player_name: str, today: date) -> dict | None:
    if report_repository.report_exists("player_daily_report", today, player_id=player_id):
        logger.info("Player report already exists, skipping: %s %s", player_name, today)
        return None

    since = today - timedelta(days=settings.report_recent_days)
    titles = _collect_recent_titles(player_id, since)
    stat_snapshot = report_repository.fetch_latest_player_stats(player_id)
    if not titles and not stat_snapshot:
        return None

    user_prompt = _build_player_prompt(player_name, titles, stat_snapshot)
    try:
        response = _get_openai().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": settings.player_system_prompt.format(team_name_ko=settings.team_name_ko)},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=settings.player_report_max_tokens,
            temperature=settings.player_report_temperature,
        )
        insight = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("Failed to generate player report for %s: %s", player_name, exc)
        return None

    return {
        "player_id": player_id,
        "date": today.isoformat(),
        "insight": insight,
        "stat_snapshot": stat_snapshot.get("raw_stats") or {},
    }


_KST = timezone(timedelta(hours=9))


def run() -> dict:
    today = datetime.now(_KST).date()
    logger.info("Report generation started: %s", today)

    team_report = _build_team_report(today)
    if team_report:
        report_repository.save_report("team_daily_report", team_report, on_conflict="date")

    saved = 0
    players = report_repository.list_active_players()
    with ThreadPoolExecutor(max_workers=_PLAYER_REPORT_WORKERS) as executor:
        futures = {
            executor.submit(_build_player_report, player["id"], player["name"], today): player
            for player in players
        }
        for future in as_completed(futures):
            report = future.result()
            if report:
                report_repository.save_report(
                    "player_daily_report",
                    report,
                    on_conflict="player_id,date",
                )
                saved += 1

    team_saved = 1 if team_report else 0
    logger.info("Report generation completed: team=%s players=%s", team_saved, saved)
    return {"team": team_saved, "players": saved}


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    result = run()
    print(result)
    sys.exit(0)
