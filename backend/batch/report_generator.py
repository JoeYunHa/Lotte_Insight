"""
일간 리포트 생성.
- 팀 리포트: 기사 분류 집계 기반 템플릿 생성 → team_daily_report
- 선수 리포트: 기사 제목 + 기록 수치를 GPT-4o mini에 전달 → player_daily_report
  (기사 원문 포함 금지 — CLAUDE.md §8 참고)
"""

import logging
from datetime import date, timedelta

from openai import OpenAI

from core.config import settings
from core.database import supabase

logger = logging.getLogger(__name__)
_openai_client: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


PLAYER_SYSTEM_PROMPT = (
    "당신은 KBO 롯데 자이언츠 전문 야구 분석가입니다. "
    "팬을 위한 선수별 인사이트 리포트를 200자 이내로 작성합니다. "
    "제공된 기사 제목 목록과 기록 수치만 활용하고, 추측성 발언은 피하세요."
)


# ── 팀 일간 리포트 ────────────────────────────────────────────────────────────

def _build_team_report(today: date) -> dict:
    articles_result = supabase.table("articles").select(
        "id, article_labels(label)"
    ).gte("published_at", f"{today}T00:00:00+00:00").lte(
        "published_at", f"{today}T23:59:59+00:00"
    ).execute()

    articles = articles_result.data
    article_ids = [a["id"] for a in articles]

    label_counts: dict[str, int] = {}
    for article in articles:
        for lbl in article.get("article_labels") or []:
            label_counts[lbl["label"]] = label_counts.get(lbl["label"], 0) + 1

    player_mentions: dict[str, int] = {}
    if article_ids:
        pm_result = supabase.table("article_players").select(
            "player_id, players(name)"
        ).in_("article_id", article_ids).execute()
        for row in pm_result.data:
            name = (row.get("players") or {}).get("name", "")
            if name:
                player_mentions[name] = player_mentions.get(name, 0) + 1

    label_summary = ", ".join(
        f"{k} {v}건"
        for k, v in sorted(label_counts.items(), key=lambda x: -x[1])
    ) or "없음"
    top_players = sorted(player_mentions.items(), key=lambda x: -x[1])[:5]
    player_summary = ", ".join(f"{n}({c})" for n, c in top_players) or "없음"

    issue_summary = (
        f"오늘 롯데 자이언츠 관련 기사 {len(articles)}건\n"
        f"분류 현황: {label_summary}\n"
        f"주요 언급 선수: {player_summary}"
    )
    top_labels = [k for k, _ in sorted(label_counts.items(), key=lambda x: -x[1])[:3]]

    return {
        "date": today.isoformat(),
        "issue_summary": issue_summary,
        "article_count": len(articles),
        "top_labels": top_labels,
    }


# ── 선수 일간 리포트 ──────────────────────────────────────────────────────────

def _build_player_report(player_id: int, player_name: str, today: date) -> dict | None:
    week_ago = today - timedelta(days=7)

    ap_result = supabase.table("article_players").select(
        "articles(title, published_at)"
    ).eq("player_id", player_id).execute()

    titles = [
        r["articles"]["title"]
        for r in ap_result.data
        if r.get("articles")
        and r["articles"].get("published_at", "") >= f"{week_ago.isoformat()}T00:00:00"
    ][:10]

    stats_result = supabase.table("player_stats_daily").select("*").eq(
        "player_id", player_id
    ).order("date", desc=True).limit(1).execute()
    stat_snapshot = stats_result.data[0] if stats_result.data else {}

    if not titles and not stat_snapshot:
        return None

    titles_text = "\n".join(f"- {t}" for t in titles) or "관련 기사 없음"
    stats_text = (
        f"타율: {stat_snapshot.get('avg', 'N/A')}, "
        f"OPS: {stat_snapshot.get('ops', 'N/A')}, "
        f"ERA: {stat_snapshot.get('era', 'N/A')}"
    ) if stat_snapshot else "기록 없음"

    user_prompt = (
        f"선수명: {player_name}\n\n"
        f"최근 7일 기사 제목:\n{titles_text}\n\n"
        f"최근 기록: {stats_text}"
    )

    try:
        response = _get_openai().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": PLAYER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        insight = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"GPT 호출 실패 ({player_name}): {e}")
        return None

    return {
        "player_id": player_id,
        "date": today.isoformat(),
        "insight": insight,
        "stat_snapshot": stat_snapshot.get("raw_stats") or {},
    }


# ── 진입점 ────────────────────────────────────────────────────────────────────

def run() -> dict:
    today = date.today()
    logger.info(f"리포트 생성 시작: {today}")

    team_report = _build_team_report(today)
    supabase.table("team_daily_report").upsert(team_report, on_conflict="date").execute()
    logger.info(f"팀 리포트 저장 — {team_report['article_count']}건 기준")

    players_result = supabase.table("players").select("id, name").eq("status", "active").execute()
    players = players_result.data

    saved = 0
    for player in players:
        report = _build_player_report(player["id"], player["name"], today)
        if report:
            supabase.table("player_daily_report").upsert(
                report, on_conflict="player_id,date"
            ).execute()
            saved += 1

    logger.info(f"선수 리포트 저장 — {saved}/{len(players)}명")
    return {"team": 1, "players": saved}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(result)
    sys.exit(0)
