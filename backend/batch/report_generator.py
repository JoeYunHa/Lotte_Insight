"""
Generate daily team and player reports.
"""

import logging
from datetime import date, timedelta

from openai import OpenAI

from core.config import settings
from services import report_repository

logger = logging.getLogger(__name__)
_openai_client: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client



def _summarize_label_counts(articles: list[dict]) -> dict[str, int]:
    label_counts: dict[str, int] = {}
    for article in articles:
        for label in article.get("article_labels") or []:
            label_name = label["label"]
            label_counts[label_name] = label_counts.get(label_name, 0) + 1
    return label_counts


def _summarize_player_mentions(mentions: list[dict]) -> dict[str, int]:
    player_mentions: dict[str, int] = {}
    for row in mentions:
        name = (row.get("players") or {}).get("name", "")
        if name:
            player_mentions[name] = player_mentions.get(name, 0) + 1
    return player_mentions


def _format_team_report(today: date, articles: list[dict], mentions: list[dict]) -> dict:
    label_counts = _summarize_label_counts(articles)
    player_mentions = _summarize_player_mentions(mentions)

    label_summary = ", ".join(
        f"{label} {count}건"
        for label, count in sorted(label_counts.items(), key=lambda item: -item[1])
    ) or "없음"
    top_players = sorted(player_mentions.items(), key=lambda item: -item[1])[:5]
    player_summary = ", ".join(f"{name}({count})" for name, count in top_players) or "없음"
    top_labels = [label for label, _ in sorted(label_counts.items(), key=lambda item: -item[1])[:3]]

    return {
        "date": today.isoformat(),
        "issue_summary": (
            f"오늘 {settings.team_name_ko} 자이언츠 관련 기사 {len(articles)}건\n"
            f"분류 현황: {label_summary}\n"
            f"주요 언급 선수: {player_summary}"
        ),
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
    return [
        row["articles"].get("event_summary") or row["articles"]["title"]
        for row in article_rows
        if row.get("articles")
    ]


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


def run() -> dict:
    today = date.today()
    logger.info("Report generation started: %s", today)

    team_report = _build_team_report(today)
    if team_report:
        report_repository.save_report("team_daily_report", team_report, on_conflict="date")

    saved = 0
    for player in report_repository.list_active_players():
        report = _build_player_report(player["id"], player["name"], today)
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
