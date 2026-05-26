"""Unit tests for RSS collector module."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from batch.rss_collector import (
    RSSFeedConfig,
    _contains_lotte_keyword,
    _parse_rss_pubdate,
    _should_include_entry,
    normalize_rss_entry,
)
from services.article_utils import normalize_url


class TestLotteKeywordFilter:
    """Test Lotte-related keyword filtering."""

    def test_contains_lotte_keyword_korean(self):
        assert _contains_lotte_keyword("롯데 자이언츠 승리")
        assert _contains_lotte_keyword("사직구장에서 경기")
        assert _contains_lotte_keyword("자이언츠 김민석 홈런")

    def test_contains_lotte_keyword_english(self):
        assert _contains_lotte_keyword("Lotte Giants win")
        assert _contains_lotte_keyword("GIANTS vs TIGERS")

    def test_contains_lotte_keyword_case_insensitive(self):
        assert _contains_lotte_keyword("LOTTE GIANTS")
        assert _contains_lotte_keyword("lotte giants")

    def test_does_not_contain_lotte_keyword(self):
        assert not _contains_lotte_keyword("삼성 라이온즈 경기")
        assert not _contains_lotte_keyword("KIA 타이거즈 승리")


class TestRSSEntryFiltering:
    """Test RSS entry filtering logic."""

    def test_should_include_entry_with_lotte_in_title(self):
        entry = Mock()
        entry.title = "롯데 자이언츠 경기"
        entry.summary = "일반 내용"
        assert _should_include_entry(entry)

    def test_should_include_entry_with_lotte_in_summary(self):
        entry = Mock()
        entry.title = "경기 결과"
        entry.summary = "롯데 자이언츠가 승리했습니다"
        assert _should_include_entry(entry)

    def test_should_exclude_entry_without_lotte(self):
        entry = Mock()
        entry.title = "삼성 경기"
        entry.summary = "삼성 라이온즈 경기"
        assert not _should_include_entry(entry)


class TestRSSPubdateParsing:
    """Test RSS publication date parsing."""

    def test_parse_rss_pubdate_with_published_parsed(self):
        entry = Mock()
        # Create a time struct for 2026-05-26 12:00:00 UTC
        import time
        entry.published_parsed = time.strptime("2026-05-26 12:00:00", "%Y-%m-%d %H:%M:%S")
        entry.updated_parsed = None

        result = _parse_rss_pubdate(entry)
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 26

    def test_parse_rss_pubdate_with_updated_parsed(self):
        entry = Mock()
        import time
        entry.published_parsed = None
        entry.updated_parsed = time.strptime("2026-05-25 10:00:00", "%Y-%m-%d %H:%M:%S")

        result = _parse_rss_pubdate(entry)
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_parse_rss_pubdate_fallback(self):
        entry = Mock()
        entry.published_parsed = None
        entry.updated_parsed = None

        result = _parse_rss_pubdate(entry)
        assert isinstance(result, datetime)
        # Should be close to current time
        now = datetime.now(timezone.utc)
        diff = abs((result - now).total_seconds())
        assert diff < 5  # Within 5 seconds


class TestNormalizeRSSEntry:
    """Test RSS entry normalization to NormalizedNewsItem."""

    def test_normalize_valid_entry(self):
        entry = Mock()
        entry.title = "롯데 자이언츠 승리"
        entry.summary = "경기 요약 내용입니다"
        entry.link = "https://news.example.com/article/123"
        import time
        entry.published_parsed = time.strptime("2026-05-26 12:00:00", "%Y-%m-%d %H:%M:%S")

        result = normalize_rss_entry(entry, source_name="test_source")

        assert result is not None
        assert result.title == "롯데 자이언츠 승리"
        assert "경기 요약" in result.description_snippet
        assert result.link == "https://news.example.com/article/123"
        assert "news.example.com" in result.source_name

    def test_normalize_entry_with_html_tags(self):
        entry = Mock()
        entry.title = "<strong>롯데</strong> 승리"
        entry.summary = "<p>경기 <b>요약</b></p>"
        entry.link = "https://news.example.com/article/123"
        import time
        entry.published_parsed = time.strptime("2026-05-26 12:00:00", "%Y-%m-%d %H:%M:%S")

        result = normalize_rss_entry(entry, source_name="test_source")

        assert result is not None
        assert result.title == "롯데 승리"
        assert result.description_snippet == "경기 요약"

    def test_normalize_entry_truncates_long_description(self):
        entry = Mock()
        entry.title = "Test"
        entry.summary = "A" * 500
        entry.link = "https://example.com"
        import time
        entry.published_parsed = time.strptime("2026-05-26 12:00:00", "%Y-%m-%d %H:%M:%S")

        result = normalize_rss_entry(
            entry, source_name="test", description_snippet_length=100
        )

        assert result is not None
        assert len(result.description_snippet) == 100

    def test_normalize_entry_missing_title(self):
        entry = Mock()
        entry.title = ""
        entry.summary = "Summary"
        entry.link = "https://example.com"

        result = normalize_rss_entry(entry, source_name="test")
        assert result is None

    def test_normalize_entry_missing_link(self):
        entry = Mock()
        entry.title = "Title"
        entry.summary = "Summary"
        entry.link = ""

        result = normalize_rss_entry(entry, source_name="test")
        assert result is None


class TestURLNormalization:
    """Test URL normalization for deduplication."""

    def test_normalize_url_removes_query_params(self):
        url = "https://example.com/article?utm_source=rss&utm_medium=feed"
        assert normalize_url(url) == "https://example.com/article"

    def test_normalize_url_removes_fragment(self):
        url = "https://example.com/article#section1"
        assert normalize_url(url) == "https://example.com/article"

    def test_normalize_url_removes_www(self):
        url = "https://www.example.com/article"
        assert normalize_url(url) == "https://example.com/article"

    def test_normalize_url_converts_http_to_https(self):
        url = "http://example.com/article"
        assert normalize_url(url) == "https://example.com/article"

    def test_normalize_url_removes_trailing_slash(self):
        url = "https://example.com/article/"
        assert normalize_url(url) == "https://example.com/article"

    def test_normalize_url_lowercase(self):
        url = "HTTPS://EXAMPLE.COM/Article"
        assert normalize_url(url) == "https://example.com/article"

    def test_normalize_url_complex(self):
        url = "HTTP://WWW.EXAMPLE.COM/Article/?utm_source=rss#top"
        assert normalize_url(url) == "https://example.com/article"

    def test_normalize_url_invalid_url_returns_original(self):
        url = "not a url"
        result = normalize_url(url)
        assert "not a url" in result.lower()


class TestRSSFeedConfig:
    """Test RSS feed configuration dataclass."""

    def test_feed_config_creation(self):
        config = RSSFeedConfig(
            name="test_feed",
            url="https://example.com/rss",
            description="Test feed",
        )
        assert config.name == "test_feed"
        assert config.url == "https://example.com/rss"
        assert config.description == "Test feed"
