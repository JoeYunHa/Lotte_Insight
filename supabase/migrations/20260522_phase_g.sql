-- Phase G 마이그레이션
-- 1. article_labels UNIQUE(article_id, label) — upsert on_conflict="article_id,label" 전제
-- 2. article_players.player_stance 컬럼 추가
-- 3. article_players UNIQUE(article_id, player_id) — upsert on_conflict 전제, 미존재 시 생성
-- Supabase SQL Editor에서 실행 완료 (2026-05-22)

-- 1. article_labels 복합 unique constraint
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'article_labels'::regclass
      AND conname = 'article_labels_article_id_label_key'
  ) THEN
    ALTER TABLE article_labels ADD CONSTRAINT article_labels_article_id_label_key
      UNIQUE (article_id, label);
  END IF;
END$$;

-- 2. article_players.player_stance 컬럼
ALTER TABLE article_players
  ADD COLUMN IF NOT EXISTS player_stance TEXT
  CHECK (player_stance IN ('positive', 'negative', 'neutral'));

-- 3. article_players UNIQUE(article_id, player_id)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'article_players'::regclass
      AND conname = 'article_players_article_id_player_id_key'
  ) THEN
    ALTER TABLE article_players ADD CONSTRAINT article_players_article_id_player_id_key
      UNIQUE (article_id, player_id);
  END IF;
END$$;
