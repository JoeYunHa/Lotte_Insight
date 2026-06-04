from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch


def test_team_prompt_includes_player_stance_distribution():
    from batch import report_generator

    prompt = report_generator._build_team_gpt_prompt(
        article_count=3,
        label_counts={"MATCH_RELATED": 2},
        player_mentions={"박세웅": 2},
        player_stances={"박세웅": {"positive": 1, "neutral": 0, "negative": 1}},
        event_texts=["롯데가 승리했다."],
    )

    assert "선수별 기사 톤 분포" in prompt
    assert "박세웅(긍정 1, 중립 0, 부정 1)" in prompt


def test_collect_recent_titles_prefixes_player_stance():
    from batch import report_generator

    rows = [
        {
            "player_stance": "negative",
            "articles": {
                "title": "박세웅 5실점",
                "event_summary": None,
            },
        }
    ]

    with (
        patch.object(report_generator.report_repository, "fetch_recent_player_articles", return_value=rows),
        patch.object(report_generator, "settings", SimpleNamespace(player_report_article_limit=10)),
    ):
        titles = report_generator._collect_recent_titles(7, date(2026, 6, 1))

    assert titles == ["[negative] 박세웅 5실점"]
