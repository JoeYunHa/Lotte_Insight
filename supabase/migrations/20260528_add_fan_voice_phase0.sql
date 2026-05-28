-- Fan Voice Phase 0 schema
-- 실행 완료(2026-05-28)

create table if not exists fan_sessions (
  id bigint generated always as identity primary key,
  session_token_hash text not null unique,
  session_alias text not null,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  write_count integer not null default 0,
  is_blocked boolean not null default false
);

create table if not exists fan_voice_messages (
  id uuid primary key default gen_random_uuid(),
  session_id bigint not null references fan_sessions(id) on delete cascade,
  context_type text not null,
  context_id text not null,
  message text not null,
  emotion_tag text,
  topic_tag text,
  player_id uuid references players(id) on delete set null,
  article_id uuid references articles(id) on delete set null,
  cluster_id text,
  game_date date,
  status text not null default 'visible',
  pinned_score numeric not null default 0,
  reaction_count integer not null default 0,
  report_count integer not null default 0,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  constraint fan_voice_messages_message_len_chk check (char_length(message) between 1 and 60),
  constraint fan_voice_messages_status_chk check (status in ('visible', 'hidden', 'flagged', 'deleted')),
  constraint fan_voice_messages_context_type_chk check (context_type in ('home', 'player', 'topic', 'game', 'label'))
);

create table if not exists fan_voice_reactions (
  id bigint generated always as identity primary key,
  message_id uuid not null references fan_voice_messages(id) on delete cascade,
  session_id bigint not null references fan_sessions(id) on delete cascade,
  reaction_type text not null,
  created_at timestamptz not null default now(),
  unique (message_id, session_id, reaction_type)
);

create table if not exists fan_voice_reports (
  id bigint generated always as identity primary key,
  message_id uuid not null references fan_voice_messages(id) on delete cascade,
  session_id bigint not null references fan_sessions(id) on delete cascade,
  reason text not null,
  created_at timestamptz not null default now(),
  unique (message_id, session_id)
);

create index if not exists fan_voice_messages_context_idx
  on fan_voice_messages (context_type, context_id, status, created_at desc);

create index if not exists fan_voice_messages_player_idx
  on fan_voice_messages (player_id, created_at desc);

create index if not exists fan_voice_messages_cluster_idx
  on fan_voice_messages (cluster_id, created_at desc);

create index if not exists fan_voice_messages_expires_idx
  on fan_voice_messages (expires_at);

create index if not exists fan_voice_reactions_message_idx
  on fan_voice_reactions (message_id);

create index if not exists fan_voice_reports_message_idx
  on fan_voice_reports (message_id);
