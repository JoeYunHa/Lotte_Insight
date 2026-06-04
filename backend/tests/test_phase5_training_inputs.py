from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "training"
if str(TRAINING) not in sys.path:
    sys.path.insert(0, str(TRAINING))


def test_team_stance_loader_accepts_phase5_column(tmp_path):
    from train.train_stance_classifier import load_data

    rows = [
        {
            "title": "롯데 승리",
            "description_snippet": "롯데가 이겼다.",
            "is_lotte_related": "true",
            "team_stance": "positive",
        },
        {
            "title": "롯데 패배",
            "description_snippet": "롯데가 졌다.",
            "is_lotte_related": "true",
            "team_stance": "negative",
        },
        {
            "title": "롯데 경기 예고",
            "description_snippet": "선발 예고.",
            "is_lotte_related": "true",
            "team_stance": "neutral",
        },
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "labeled_titles.csv", index=False, encoding="utf-8-sig")

    titles, snippets, labels = load_data(tmp_path)

    assert titles == ["롯데 승리", "롯데 패배", "롯데 경기 예고"]
    assert snippets == ["롯데가 이겼다.", "롯데가 졌다.", "선발 예고."]
    assert sorted(labels) == [0, 1, 2]


def test_player_stance_loader_excludes_event_summary(tmp_path):
    from train.train_player_stance_classifier import load_data

    rows = [
        {
            "title": "박세웅 호투",
            "description_snippet": "7이닝 무실점",
            "event_summary": "이 문장은 학습 입력에 들어가면 안 된다",
            "query_player": "박세웅",
            "player_stance": "positive",
        },
        {
            "title": "박세웅 부진",
            "description_snippet": "5실점",
            "event_summary": "제외 대상",
            "query_player": "박세웅",
            "player_stance": "negative",
        },
        {
            "title": "박세웅 선발 예고",
            "description_snippet": "내일 등판",
            "event_summary": "제외 대상",
            "query_player": "박세웅",
            "player_stance": "neutral",
        },
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "labeled_players.csv", index=False, encoding="utf-8-sig")

    _titles, player_snippets, _labels = load_data(tmp_path)

    assert player_snippets[0] == "박세웅 7이닝 무실점"
    assert "학습 입력" not in " ".join(player_snippets)
