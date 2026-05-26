# RSS Feeds Integration Guide

## Overview

As of 2026-05-26, Lotte Insight collects articles from multiple sources:
- **Naver Search API** (existing)
- **RSS Feeds** (new - Phase 1)

This expands coverage while maintaining the metadata-only policy.

## Current RSS Feed Sources

### Active Sources (Last verified: 2026-05-26)

1. **Google News - 롯데 자이언츠**
   - URL: `https://news.google.com/rss/search?q=롯데+자이언츠&hl=ko&gl=KR&ceid=KR:ko`
   - Coverage: Aggregated Korean news for "롯데 자이언츠"
   - Filtering: Pre-filtered by Google
   - Status: ✅ Working (92 items/day average)

2. **Google News - KBO 롯데**
   - URL: `https://news.google.com/rss/search?q=KBO+롯데&hl=ko&gl=KR&ceid=KR:ko`
   - Coverage: Aggregated Korean news for "KBO 롯데"
   - Filtering: Pre-filtered by Google
   - Status: ✅ Working (77 items/day average)

3. **동아일보 (Donga) - 스포츠**
   - URL: `http://rss.donga.com/sports.xml`
   - Coverage: General sports news from major Korean newspaper
   - Filtering: Client-side keyword matching
   - Status: ✅ Working (2 items/day average after filtering)

4. **스포츠경향 (Sports Khan) - 야구** ⭐ NEW
   - URL: `https://sports.khan.co.kr/rss/baseball`
   - Coverage: Baseball-specific Korean sports news
   - Filtering: Client-side keyword matching
   - Status: ✅ Working (4 items/day average after filtering)
   - Note: Fixed URL (changed from `/rss` to `/rss/baseball`)

5. **연합뉴스 (Yonhap) - 스포츠** ⭐ NEW
   - URL: `https://www.yna.co.kr/rss/sports.xml`
   - Coverage: Sports news from Korea's major news agency
   - Filtering: Client-side keyword matching
   - Status: ✅ Working (4 items/day average after filtering)
   - Note: Fixed URL (changed domain from `yonhapnews.co.kr` to `yna.co.kr`), requires SSL verify=False

**Total Daily Collection Capacity: ~179 items**

### Permanently Disabled Sources (RSS service discontinued)

6. **스포츠월드 (Sports World) - 야구**
   - URL: `http://rss.sportsworldi.com/sw_baseball.xml`
   - Status: ❌ Server unreachable (connection timeout)
   - Action: RSS server appears to be down permanently

7. **중앙일보 (Joins MSN) - 스포츠**
   - URL: `http://rss.joinsmsn.com/joins_sports_list.xml`
   - Status: ❌ RSS service discontinued (returns HTML page instead of XML)
   - Action: Service no longer available

8. **MBC - 스포츠 뉴스**
   - URL: `http://imnews.imbc.com/rss/news/news_07.xml`
   - Status: ❌ RSS service discontinued (returns HTML page instead of XML)
   - Action: Service no longer available

## Architecture

### Collection Flow

```
news_collector.py (main pipeline)
├─ Phase 1: Naver Search API
│  └─ Parallel keyword queries
├─ Phase 2: RSS Feeds
│  └─ rss_collector.collect_from_rss_feeds()
├─ Phase 3: Normalization & Deduplication
│  └─ URL normalization (removes query params, www, fragments)
├─ Phase 4: Inference
│  └─ Classification, stance, summarization
└─ Phase 5: Database upsert
   └─ Includes collection_source tracking
```

### Deduplication Strategy

URLs are normalized before deduplication:
- `http://` → `https://`
- `www.example.com` → `example.com`
- Query parameters removed
- Fragments removed
- Trailing slashes removed
- Lowercase conversion

Example:
```
HTTP://WWW.EXAMPLE.COM/Article/?utm_source=rss#top
↓
https://example.com/article
```

## Database Schema Changes

### New Column: `articles.collection_source`

Migration: `supabase/migrations/20260526_add_collection_source.sql`

```sql
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS collection_source TEXT DEFAULT 'naver_api';
```

Possible values (Active sources):
- `naver_api` - Naver Search API
- `rss_google_news_lotte` - Google News (롯데 자이언츠)
- `rss_google_news_kbo` - Google News (KBO 롯데)
- `rss_donga_sports` - 동아일보 스포츠 RSS
- `rss_khan_baseball` - 스포츠경향 야구 RSS (NEW)
- `rss_yonhap_sports` - 연합뉴스 스포츠 RSS (NEW)

Possible values (Permanently disabled):
- `rss_sportsworld_baseball` - 스포츠월드 야구 RSS (server down)
- `rss_joins_sports` - 중앙일보 스포츠 RSS (service discontinued)
- `rss_mbc_sports` - MBC 스포츠 뉴스 RSS (service discontinued)

## Testing RSS Collector Standalone

```bash
cd backend
python -m batch.rss_collector
```

This will:
1. Fetch from all configured RSS feeds
2. Filter Lotte-related articles
3. Print first 10 items
4. Return count

## Adding New RSS Feeds

Edit `backend/batch/rss_collector.py`:

```python
RSS_FEEDS = [
    # ... existing feeds ...
    (
        "new_feed_name",
        "https://example.com/rss",
        "Description of the feed",
    ),
]
```

The `collection_source` will be auto-generated as `rss_{feed_name}`.

## Keyword Filtering

Articles are filtered for Lotte-related content using keywords:

```python
LOTTE_KEYWORDS = [
    "롯데",
    "lotte",
    "자이언츠",
    "giants",
    "사직",
    "sajik",
]
```

Filtering is case-insensitive and checks both title and summary.

## Performance Notes

- RSS feeds are fetched sequentially (not parallelized)
- Typical collection time: 5-10 seconds for all feeds
- Network errors are logged but don't block other feeds
- Invalid/malformed RSS entries are skipped gracefully
- SSL certificate verification is disabled for feeds with certificate issues (e.g., Yonhap News)
- Total daily collection capacity: ~179 items across all active sources

## Migration Checklist

Before deploying to production:

1. ✅ Install `feedparser` dependency
   ```bash
   pip install -r requirements.txt
   ```

2. ✅ Run Supabase migration
   ```sql
   -- Execute in Supabase SQL Editor
   -- supabase/migrations/20260526_add_collection_source.sql
   ```

3. ✅ Run unit tests
   ```bash
   pytest tests/test_rss_collector.py -v
   pytest tests/test_article_utils.py::TestNormalizeURL -v
   ```

4. ⏳ Test end-to-end collection
   ```bash
   python -m batch.news_collector
   ```

5. ⏳ Verify database records have `collection_source` populated
   ```sql
   SELECT collection_source, COUNT(*)
   FROM articles
   WHERE DATE(published_at) = CURRENT_DATE
   GROUP BY collection_source;
   ```

## Future Expansion (Phase 3)

Candidate sources for future integration:
- Kakao/Daum Search API (web documents)
- OSEN sports RSS (if available)
- Spotv News RSS (if available)
- Team-specific news sources
- Source quality weighting system

## Legal Compliance

All RSS sources comply with the metadata-only policy:
- Only title, URL, source, timestamp, and description snippet are stored
- No full article bodies
- Users are directed to original sources for full content
- Respects robots.txt and feed provider terms
