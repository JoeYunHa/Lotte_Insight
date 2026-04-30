"""
Generate daily team and player reports.
"""

import logging
from datetime import date, timedelta

from openai import OpenAI

from core.config import settings
from core.database import supabase
from core.time_utils import utc_day_bounds

logger = logging.getLogger(__name__)
_openai_client: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


PLAYER_SYSTEM_PROMPT = (
    f"당신은 KBO {settings.team_name_ko} 자이언츠 전문 야구 분석가입니다. "
    "선수를 위한 선수별 인사이트 리포트를 200자 이내로 작성합니다. "
    "제공된 기사 제목 목록과 기록 수치만 사용하고, 추측성 발언은 하지 마세요."
)


def _build_team_report(today: date) -> dict:
    start_at, end_at = utc_day_bounds(today)
    articles_result = (
        supabase.table("articles")
        .select("id, article_labels(label)")
        .gte("published_at", start_at)
        .lte("published_at", end_at)
        .execute()
    )

    articles = articles_result.data
    article_ids = [article["id"] for article in articles]

    label_counts: dict[str, int] = {}
    for article in articles:
        for label in article.get("article_labels") or []:
            key = label["label"]
            label_counts[key] = label_counts.get(key, 0) + 1

    player_mentions: dict[str, int] = {}
    if article_ids:
        mention_result = (
            supabase.table("article_players")
            .select("player_id, players(name)")
            .in_("article_id", article_ids)
            .execute()
        )
        for row in mention_result.data:
            name = (row.get("players") or {}).get("name", "")
            if name:
                player_mentions[name] = player_mentions.get(name, 0) + 1

    label_summary = ", ".join(
        f"{label} {count}건"
        for label, count in sorted(label_counts.items(), key=lambda item: -item[1])
    ) or "없음"
    top_players = sorted(player_mentions.items(), key=lambda item: -item[1])[:5]
    player_summary = ", ".join(f"{name}({count})" for name, count in top_players) or "없음"

    issue_summary = (
        f"오늘 {settings.team_name_ko} 자이언츠 관련 기사 {len(articles)}건\n"
        f"분류 현황: {label_summary}\n"
        f"주요 언급 선수: {player_summary}"
    )
    top_labels = [label for label, _ in sorted(label_counts.items(), key=lambda item: -item[1])[:3]]

    return {
        "date": today.isoformat(),
        "issue_summary": issue_summary,
        "article_count": len(articles),
        "top_labels": top_labels,
    }


def _build_player_report(player_id: int, player_name: str, today: date) -> dict | None:
    since = today - timedelta(days=settings.report_recent_days)

    article_result = (
        supabase.table("article_players")
        .select("articles(title, published_at)")
        .eq("player_id", player_id)
        .execute()
    )
    titles = [
        row["articles"]["title"]
        for row in article_result.data
        if row.get("articles")
        and row["articles"].get("published_at", "") >= f"{since.isoformat()}T00:00:00"
    ][: settings.player_report_article_limit]

    stats_result = (
        supabase.table("player_stats_daily")
        .select("*")
        .eq("player_id", player_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    stat_snapshot = stats_result.data[0] if stats_result.data else {}

    if not titles and not stat_snapshot:
        return None

    titles_text = "\n".join(f"- {title}" for title in titles) or "관련 기사 없음"
    stats_text = (
        f"타율 {stat_snapshot.get('avg', 'N/A')}, "
        f"OPS {stat_snapshot.get('ops', 'N/A')}, "
        f"ERA {stat_snapshot.get('era', 'N/A')}"
    ) if stat_snapshot else "기록 없음"

    user_prompt = (
        f"선수명: {player_name}\n\n"
        f"최근 기사 제목:\n{titles_text}\n\n"
        f"최근 기록: {stats_text}"
    )

    try:
        response = _get_openai().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": PLAYER_SYSTEM_PROMPT},
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


def run() -> dict:
    today = date.today()
    logger.info("Report generation started: %s", today)

    team_report = _build_team_report(today)
    supabase.table("team_daily_report").upsert(team_report, on_conflict="date").execute()

    players_result = supabase.table("players").select("id, name").eq("status", "active").execute()
    saved = 0
    for player in players_result.data:
        report = _build_player_report(player["id"], player["name"], today)
        if report:
            supabase.table("player_daily_report").upsert(
                report,
                on_conflict="player_id,date",
            ).execute()
            saved += 1

    logger.info("Report generation completed: team=1 players=%s", saved)
    return {"team": 1, "players": saved}


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    result = run()
    print(result)
    sys.exit(0)
