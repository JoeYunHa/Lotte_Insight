"""Unit tests for services/home_service.py."""
import json
from datetime import date
from unittest.mock import MagicMock, patch

from services import home_service


def _make_article(
    label: str = "MATCH_RELATED",
    stance: str | None = None,
    title: str = "Test",
    article_id: int = 1,
) -> dict:
    summary = (
        json.dumps({"lotte_stance": stance, "event_summary": "요약", "key_players": []},
                   ensure_ascii=False)
        if stance else None
    )
    return {
        "id": article_id,
        "title": title,
        "event_summary": summary,
        "article_labels": [{"label": label, "confidence": 0.9}],
    }


class TestComputeLabelCounts:
    def test_counts_labels(self):
        articles = [
            _make_article("MATCH_RELATED", article_id=1),
            _make_article("MATCH_RELATED", article_id=2),
            _make_article("INJURY_ROSTER", article_id=3),
        ]
        counts = home_service._compute_label_counts(articles)
        assert counts["MATCH_RELATED"] == 2
        assert counts["INJURY_ROSTER"] == 1
        assert counts["ETC"] == 0

    def test_empty_articles(self):
        counts = home_service._compute_label_counts([])
        assert all(v == 0 for v in counts.values())

    def test_unknown_label_not_in_counts(self):
        articles = [_make_article("UNKNOWN_LABEL")]
        counts = home_service._compute_label_counts(articles)
        assert "UNKNOWN_LABEL" not in counts


class TestComputeSentiment:
    def test_ratios_sum_correctly(self):
        articles = [
            _make_article(stance="positive", article_id=1),
            _make_article(stance="positive", article_id=2),
            _make_article(stance="negative", article_id=3),
        ]
        sentiment = home_service._compute_sentiment(articles)
        assert abs(sentiment["positive"] - 2 / 3) < 1e-9
        assert abs(sentiment["negative"] - 1 / 3) < 1e-9
        assert sentiment["analyzed"] == 3

    def test_no_stance_returns_zeros(self):
        articles = [_make_article()]
        sentiment = home_service._compute_sentiment(articles)
        assert sentiment["positive"] == 0.0
        assert sentiment["neutral"] == 0.0
        assert sentiment["negative"] == 0.0
        assert sentiment["analyzed"] == 0

    def test_neutral_counted(self):
        articles = [_make_article(stance="neutral", article_id=1)]
        sentiment = home_service._compute_sentiment(articles)
        assert sentiment["neutral"] == 1.0
        assert sentiment["analyzed"] == 1


class TestGetLeadLabel:
    def test_returns_max_label(self):
        counts = {"MATCH_RELATED": 5, "INJURY_ROSTER": 2, "ETC": 0}
        assert home_service._get_lead_label(counts) == "MATCH_RELATED"

    def test_all_zero_returns_none(self):
        counts = {"MATCH_RELATED": 0, "ETC": 0}
        assert home_service._get_lead_label(counts) is None


class TestGetLeadStory:
    def test_no_lead_label_returns_none(self):
        summary, players = home_service._get_lead_story([], None)
        assert summary is None
        assert players == []

    def test_uses_longest_summary(self):
        articles = [
            _make_article("MATCH_RELATED", stance="positive", title="짧은"),
            _make_article("MATCH_RELATED", article_id=2),
        ]
        articles[0]["event_summary"] = json.dumps(
            {"lotte_stance": "positive", "event_summary": "긴 요약입니다 매우 길어요", "key_players": ["전준우"]},
            ensure_ascii=False,
        )
        articles[1]["event_summary"] = json.dumps(
            {"lotte_stance": "positive", "event_summary": "짧음", "key_players": []},
            ensure_ascii=False,
        )
        summary, players = home_service._get_lead_story(articles, "MATCH_RELATED")
        assert summary == "긴 요약입니다 매우 길어요"
        assert "전준우" in players

    def test_falls_back_to_title_when_no_summary(self):
        articles = [_make_article("MATCH_RELATED", title="타이틀 기사")]
        summary, _ = home_service._get_lead_story(articles, "MATCH_RELATED")
        assert summary == "타이틀 기사"

    def test_deduplicates_key_players(self):
        articles = []
        for i in range(3):
            a = _make_article("MATCH_RELATED", article_id=i)
            a["event_summary"] = json.dumps(
                {"lotte_stance": "positive", "event_summary": "요약", "key_players": ["전준우"]},
                ensure_ascii=False,
            )
            articles.append(a)
        _, players = home_service._get_lead_story(articles, "MATCH_RELATED")
        assert players.count("전준우") == 1


class TestComputeTopPlayers:
    def test_aggregates_mention_counts(self):
        mentions = [
            {"player_id": 1, "players": {"id": 1, "name": "홍길동", "position": "투수"}},
            {"player_id": 1, "players": {"id": 1, "name": "홍길동", "position": "투수"}},
            {"player_id": 2, "players": {"id": 2, "name": "김철수", "position": "타자"}},
        ]
        top = home_service._compute_top_players(mentions)
        assert top[0]["player"]["id"] == 1
        assert top[0]["mention_count"] == 2
        assert top[1]["mention_count"] == 1

    def test_empty_mentions(self):
        assert home_service._compute_top_players([]) == []

    def test_limit_applied(self):
        mentions = [
            {"player_id": i, "players": {"id": i, "name": f"선수{i}", "position": "타자"}}
            for i in range(10)
        ]
        top = home_service._compute_top_players(mentions, limit=3)
        assert len(top) == 3


class TestBuildHomeReport:
    def test_returns_expected_keys(self):
        target = date(2026, 5, 22)
        with (
            patch.object(home_service.report_repository, "fetch_articles_for_day", return_value=[]),
            patch.object(home_service.report_repository, "fetch_player_mentions_with_position", return_value=[]),
            patch.object(home_service.report_repository, "get_report", return_value=None),
            patch.object(home_service.report_repository, "fetch_games_for_day", return_value=[]),
        ):
            report = home_service.build_home_report(target)
        assert report["date"] == "2026-05-22"
        assert report["article_count"] == 0
        for key in ("label_counts", "sentiment", "lead_label", "top_players", "team_report", "game_context", "game_contexts"):
            assert key in report

    def test_passes_articles_to_sentiment(self):
        target = date(2026, 5, 22)
        articles = [_make_article(stance="positive")]
        with (
            patch.object(home_service.report_repository, "fetch_articles_for_day", return_value=articles),
            patch.object(home_service.report_repository, "fetch_player_mentions_with_position", return_value=[]),
            patch.object(home_service.report_repository, "get_report", return_value=None),
            patch.object(home_service.report_repository, "fetch_games_for_day", return_value=[]),
        ):
            report = home_service.build_home_report(target)
        assert report["sentiment"]["positive"] == 1.0

    def test_exposes_all_games_and_primary_game(self):
        target = date(2026, 5, 22)
        games = [
            {"date": "2026-05-22", "game_seq": 1, "opponent": "A"},
            {"date": "2026-05-22", "game_seq": 2, "opponent": "B"},
        ]
        with (
            patch.object(home_service.report_repository, "fetch_articles_for_day", return_value=[]),
            patch.object(home_service.report_repository, "fetch_player_mentions_with_position", return_value=[]),
            patch.object(home_service.report_repository, "get_report", return_value=None),
            patch.object(home_service.report_repository, "fetch_games_for_day", return_value=games),
        ):
            report = home_service.build_home_report(target)
        assert report["game_context"] == games[0]
        assert report["game_contexts"] == games
