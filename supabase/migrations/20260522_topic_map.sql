-- Topic Map 마이그레이션
-- article_topic_points: 기사별 2D 좌표 + 클러스터 소속
-- topic_clusters:       클러스터별 요약 메타데이터
-- Supabase SQL Editor에서 실행 완료(2026-05-22)

-- 1. topic_clusters (article_topic_points 외래키 참조 대상이므로 먼저 생성)
CREATE TABLE IF NOT EXISTS topic_clusters (
  id              TEXT PRIMARY KEY,                          -- e.g. "2026-05-22_c01"
  map_date        DATE NOT NULL,
  article_count   INTEGER NOT NULL,
  representative_article_id UUID REFERENCES articles(id) ON DELETE SET NULL,
  title           TEXT,
  summary         TEXT,
  label_hint      TEXT,
  key_players     TEXT[] NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS topic_clusters_map_date_idx ON topic_clusters(map_date);

-- 2. article_topic_points
CREATE TABLE IF NOT EXISTS article_topic_points (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  map_date         DATE NOT NULL,
  article_id       UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  cluster_id       TEXT REFERENCES topic_clusters(id) ON DELETE SET NULL,
  cluster_rank     INTEGER,
  x                DOUBLE PRECISION NOT NULL,
  y                DOUBLE PRECISION NOT NULL,
  embedding_model  TEXT NOT NULL,
  projection_model TEXT NOT NULL,
  is_outlier       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (map_date, article_id)
);

CREATE INDEX IF NOT EXISTS article_topic_points_map_date_idx         ON article_topic_points(map_date);
CREATE INDEX IF NOT EXISTS article_topic_points_map_date_cluster_idx ON article_topic_points(map_date, cluster_id);
CREATE INDEX IF NOT EXISTS article_topic_points_article_id_idx       ON article_topic_points(article_id);

-- 3. RLS (기존 테이블 정책과 동일: 읽기 공개, 쓰기 service role 전용)
ALTER TABLE topic_clusters      ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_topic_points ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'topic_clusters' AND policyname = 'topic_clusters_read_public'
  ) THEN
    CREATE POLICY topic_clusters_read_public
      ON topic_clusters FOR SELECT USING (TRUE);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'article_topic_points' AND policyname = 'article_topic_points_read_public'
  ) THEN
    CREATE POLICY article_topic_points_read_public
      ON article_topic_points FOR SELECT USING (TRUE);
  END IF;
END$$;
