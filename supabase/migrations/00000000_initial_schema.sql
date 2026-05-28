-- Initial Schema for Lotte Insight Project
-- 이 파일은 새 Supabase 프로젝트에서 최초 1회 실행하는 초기 스키마입니다.
-- 기존 프로젝트에는 이미 적용되어 있으므로 실행하지 마세요.
-- 
-- 실행 순서:
-- 1. 이 파일 실행 (초기 테이블 생성)
-- 2. 나머지 마이그레이션 파일들 순서대로 실행
--
-- 작성일: 2026-05-28

-- ====================
-- 1. PLAYERS 테이블
-- ====================
CREATE TABLE IF NOT EXISTS players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  name_variants TEXT[] DEFAULT '{}',
  position TEXT,
  status TEXT CHECK (status IN ('active', 'inactive', 'military', 'retired')),
  number TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);
CREATE INDEX IF NOT EXISTS idx_players_status ON players(status);

COMMENT ON TABLE players IS '롯데 자이언츠 선수 정보 (로스터)';
COMMENT ON COLUMN players.name_variants IS '선수 이름 별칭 목록 (기사 매칭용)';
COMMENT ON COLUMN players.status IS 'active: 현역, inactive: 비활성, military: 군입대, retired: 은퇴';

-- ====================
-- 2. GAMES 테이블
-- ====================
CREATE TABLE IF NOT EXISTS games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL,
  opponent TEXT,
  result TEXT CHECK (result IN ('win', 'loss', 'draw', 'cancelled')),
  score TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- game_seq 컬럼은 20260526_games_doubleheader_support.sql에서 추가됨
CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);

COMMENT ON TABLE games IS 'KBO 경기 일정 및 결과';
COMMENT ON COLUMN games.result IS 'win: 승, loss: 패, draw: 무, cancelled: 취소';

-- ====================
-- 3. ARTICLES 테이블
-- ====================
CREATE TABLE IF NOT EXISTS articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_name TEXT,
  source_url TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  published_at TIMESTAMPTZ,
  author_name TEXT,
  event_summary JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- collection_source 컬럼은 20260526_add_collection_source.sql에서 추가됨
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source_url ON articles(source_url);

COMMENT ON TABLE articles IS '수집된 뉴스 기사 메타데이터 (본문 미저장)';
COMMENT ON COLUMN articles.event_summary IS 'GPT 생성 요약 JSON: {summary, key_players, is_lotte_related, lotte_stance}';

-- ====================
-- 4. ARTICLE_LABELS 테이블
-- ====================
CREATE TABLE IF NOT EXISTS article_labels (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  confidence DOUBLE PRECISION,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- UNIQUE 제약은 20260522_phase_g.sql에서 추가됨
CREATE INDEX IF NOT EXISTS idx_article_labels_article_id ON article_labels(article_id);
CREATE INDEX IF NOT EXISTS idx_article_labels_label ON article_labels(label);

COMMENT ON TABLE article_labels IS '기사별 분류 레이블 (멀티레이블)';
COMMENT ON COLUMN article_labels.label IS 'INJURY_ROSTER, TRANSACTION_CONTRACT, MATCH_RELATED, PERFORMANCE_ANALYSIS, INTERVIEW, CLUB_OPERATION, ETC';

-- ====================
-- 5. ARTICLE_PLAYERS 테이블
-- ====================
CREATE TABLE IF NOT EXISTS article_players (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- player_stance 컬럼과 UNIQUE 제약은 20260522_phase_g.sql에서 추가됨
CREATE INDEX IF NOT EXISTS idx_article_players_article_id ON article_players(article_id);
CREATE INDEX IF NOT EXISTS idx_article_players_player_id ON article_players(player_id);

COMMENT ON TABLE article_players IS '기사-선수 연관 관계 (언급된 선수)';

-- ====================
-- 6. PLAYER_STATS_DAILY 테이블
-- ====================
CREATE TABLE IF NOT EXISTS player_stats_daily (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  avg DOUBLE PRECISION,
  ops DOUBLE PRECISION,
  era DOUBLE PRECISION,
  raw_stats JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, date)
);

CREATE INDEX IF NOT EXISTS idx_player_stats_daily_player_date ON player_stats_daily(player_id, date DESC);

COMMENT ON TABLE player_stats_daily IS '선수별 일별 통계 스냅샷';
COMMENT ON COLUMN player_stats_daily.avg IS '타자: 타율';
COMMENT ON COLUMN player_stats_daily.ops IS '타자: OPS (출루율 + 장타율)';
COMMENT ON COLUMN player_stats_daily.era IS '투수: 평균자책점';
COMMENT ON COLUMN player_stats_daily.raw_stats IS 'KBO 크롤링 원본 통계 JSON';

-- ====================
-- 7. TEAM_DAILY_REPORT 테이블
-- ====================
CREATE TABLE IF NOT EXISTS team_daily_report (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL UNIQUE,
  issue_summary TEXT,
  article_count INTEGER,
  top_labels TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_team_daily_report_date ON team_daily_report(date DESC);

COMMENT ON TABLE team_daily_report IS '팀 일별 종합 리포트';
COMMENT ON COLUMN team_daily_report.issue_summary IS '주요 이슈 요약';
COMMENT ON COLUMN team_daily_report.top_labels IS '빈도 높은 레이블 목록';

-- ====================
-- 8. PLAYER_DAILY_REPORT 테이블
-- ====================
CREATE TABLE IF NOT EXISTS player_daily_report (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  insight TEXT,
  stat_snapshot JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, date)
);

CREATE INDEX IF NOT EXISTS idx_player_daily_report_player_date ON player_daily_report(player_id, date DESC);

COMMENT ON TABLE player_daily_report IS '선수별 일별 인사이트 리포트';
COMMENT ON COLUMN player_daily_report.insight IS 'GPT 생성 선수 분석 텍스트';
COMMENT ON COLUMN player_daily_report.stat_snapshot IS '해당 날짜의 통계 스냅샷 JSON';

-- ====================
-- 9. RLS 정책 (읽기 공개)
-- ====================
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_players ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_stats_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_daily_report ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_daily_report ENABLE ROW LEVEL SECURITY;

-- 모든 사용자 읽기 허용 (public access)
CREATE POLICY players_read_public ON players FOR SELECT USING (TRUE);
CREATE POLICY games_read_public ON games FOR SELECT USING (TRUE);
CREATE POLICY articles_read_public ON articles FOR SELECT USING (TRUE);
CREATE POLICY article_labels_read_public ON article_labels FOR SELECT USING (TRUE);
CREATE POLICY article_players_read_public ON article_players FOR SELECT USING (TRUE);
CREATE POLICY player_stats_daily_read_public ON player_stats_daily FOR SELECT USING (TRUE);
CREATE POLICY team_daily_report_read_public ON team_daily_report FOR SELECT USING (TRUE);
CREATE POLICY player_daily_report_read_public ON player_daily_report FOR SELECT USING (TRUE);

-- 쓰기는 Service Role만 가능 (RLS 우회)
-- 별도 쓰기 정책 불필요

-- ====================
-- 완료
-- ====================
-- 다음 단계: 나머지 마이그레이션 파일들을 순서대로 실행
-- - 20260512_games_add_columns.sql
-- - 20260522_phase_g.sql
-- - 20260522_topic_map.sql
-- - 20260523_topic_map_replace_rpc.sql
-- - 20260524_topic_map_rpc_search_path.sql
-- - 20260526_add_collection_source.sql
-- - 20260526_games_doubleheader_support.sql
