-- Phase 5: player nickname aliases for rule-based player matching.

CREATE TABLE IF NOT EXISTS player_nicknames (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
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
