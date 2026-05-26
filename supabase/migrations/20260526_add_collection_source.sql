-- Add collection_source column to track data source origin
-- Migration: 20260526_add_collection_source
-- Purpose: Track whether articles were collected from Naver API, RSS feeds, or other sources
-- Date: 2026-05-26

-- Add collection_source column with default value
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS collection_source TEXT DEFAULT 'naver_api';

-- Add comment for documentation
COMMENT ON COLUMN articles.collection_source IS 'Source of article collection: naver_api, rss_khan, rss_google, kakao_api, etc.';

-- Create index for filtering by collection source (optional, for analytics)
CREATE INDEX IF NOT EXISTS idx_articles_collection_source
ON articles(collection_source);

-- Update existing rows to have explicit source
UPDATE articles
SET collection_source = 'naver_api'
WHERE collection_source IS NULL;
