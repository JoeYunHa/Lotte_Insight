-- games 테이블에 경기 상세 컬럼 추가
-- game_collector.py가 venue, home_away, game_time을 upsert하기 위해 필요
-- on_conflict="date" 를 사용하므로 date 컬럼에 UNIQUE 제약이 있어야 함
-- 현재 supabase sql editor에서 실행 완료한 상황(2026.05.12 15:29)

ALTER TABLE games ADD COLUMN IF NOT EXISTS venue TEXT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS home_away TEXT;  -- '홈' or '원정'
ALTER TABLE games ADD COLUMN IF NOT EXISTS game_time TEXT;  -- '18:30'

-- date 컬럼 UNIQUE 제약 (upsert on_conflict="date" 전제)
-- 이미 있으면 무시됨
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'games'::regclass AND conname = 'games_date_key'
  ) THEN
    ALTER TABLE games ADD CONSTRAINT games_date_key UNIQUE (date);
  END IF;
END$$;
