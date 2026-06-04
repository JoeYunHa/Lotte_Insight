from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_build_naver_date_url_uses_single_day_nso_filter():
    from training.collect.collect_naver_date_range import build_naver_date_url

    url = build_naver_date_url(query="롯데 자이언츠", target_date=date(2025, 3, 1), start=11)
    params = parse_qs(urlparse(url).query)

    assert params["where"] == ["news"]
    assert params["query"] == ["롯데 자이언츠"]
    assert params["nso"] == ["so:r,p:from20250301to20250301,a:all"]
    assert params["start"] == ["11"]


def test_parse_search_results_extracts_title_url_and_snippet():
    from training.collect.collect_naver_date_range import parse_search_results

    html = """
    <div class="news_area">
      <a class="news_tit" href="https://sports.example.com/a" title="롯데 승리">ignored</a>
      <div class="news_dsc">롯데가 개막전에서 승리했다.</div>
    </div>
    """

    rows = parse_search_results(html, search_date=date(2025, 3, 1))

    assert len(rows) == 1
    assert rows[0].title == "롯데 승리"
    assert rows[0].source_url == "https://sports.example.com/a"
    assert rows[0].description_snippet == "롯데가 개막전에서 승리했다."
    assert rows[0].search_date == "2025-03-01"
