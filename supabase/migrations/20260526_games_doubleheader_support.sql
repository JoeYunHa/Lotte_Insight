-- Enable doubleheader support in games table.
-- 기존 UNIQUE(date) 제약을 (date, game_seq)로 대체하여
-- 같은 날짜의 복수 경기를 저장할 수 있도록 한다.
-- 실행 완료 2026-05-28

ALTER TABLE games
ADD COLUMN IF NOT EXISTS game_seq INTEGER;

-- Backfill existing rows.
UPDATE games
SET game_seq = 1
WHERE game_seq IS NULL;

-- Ensure duplicate date rows are assigned deterministic sequence values.
WITH ranked AS (
  SELECT
    ctid,
    ROW_NUMBER() OVER (
      PARTITION BY date
      ORDER BY
        CASE WHEN game_time IS NULL OR game_time = '' THEN 1 ELSE 0 END,
        game_time ASC,
        opponent ASC
    ) AS seq
  FROM games
)
UPDATE games g
SET game_seq = r.seq
FROM ranked r
WHERE g.ctid = r.ctid
  AND (g.game_seq IS NULL OR g.game_seq <> r.seq);

ALTER TABLE games
ALTER COLUMN game_seq SET NOT NULL;

-- Drop legacy unique(date) if present.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'games'::regclass
      AND conname = 'games_date_key'
  ) THEN
    ALTER TABLE games DROP CONSTRAINT games_date_key;
  END IF;
END
$$;

-- New uniqueness for doubleheaders.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'games'::regclass
      AND conname = 'games_date_game_seq_key'
  ) THEN
    ALTER TABLE games
    ADD CONSTRAINT games_date_game_seq_key UNIQUE (date, game_seq);
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_games_date
ON games (date);
