-- Fix player_nicknames.player_id from BIGINT to UUID to match players.id type.
-- The original migration used BIGINT, but players.id is UUID; the FK would fail.
--
-- PRECONDITION: This migration must be run before any nickname rows are inserted.
-- The DROP TABLE below is safe only on an empty table. If the table already has data,
-- use ALTER TABLE ... ALTER COLUMN player_id TYPE UUID USING player_id::text::uuid instead.

BEGIN;

DO $$
BEGIN
  IF (SELECT COUNT(*) FROM player_nicknames) > 0 THEN
    RAISE EXCEPTION
      'player_nicknames is not empty (% rows). '
      'Cannot safely drop and recreate. '
      'Migrate existing rows manually before running this fix.',
      (SELECT COUNT(*) FROM player_nicknames);
  END IF;
END $$;

DROP TABLE IF EXISTS player_nicknames;

CREATE TABLE player_nicknames (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  nickname TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'manual',
  confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  valid_from TIMESTAMPTZ DEFAULT NULL,
  valid_until TIMESTAMPTZ DEFAULT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, nickname)
);

CREATE INDEX IF NOT EXISTS idx_player_nicknames_player_id ON player_nicknames(player_id);
CREATE INDEX IF NOT EXISTS idx_player_nicknames_nickname ON player_nicknames(nickname);

COMMENT ON TABLE player_nicknames IS 'Additional player aliases/nicknames used for article matching and labeling.';
COMMENT ON COLUMN player_nicknames.source IS 'manual, gpt_discovered, imported, or other source label.';

COMMIT;
