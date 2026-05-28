-- Fan Voice Opinion Review v2 schema
-- 실행 완료(2026-05-28)

create table if not exists fan_voice_daily_reviews (
  id bigint generated always as identity primary key,
  game_date date not null,
  context_key text not null default 'home:today',
  source_scope text not null check (source_scope in ('today', 'latest_fallback')),
  message_count integer not null default 0,
  unique_user_count integer not null default 0,
  summary_title text not null,
  summary_body text not null,
  highlights jsonb not null default '[]'::jsonb,
  caution_notes jsonb not null default '[]'::jsonb,
  review_type text not null default 'final' check (review_type in ('interim', 'final')),
  generated_by text not null default 'rule_v1',
  generation_version text not null default 'v1.0',
  generated_at timestamptz not null default now(),
  generation_status text not null default 'completed' check (generation_status in ('generating', 'completed', 'failed')),
  lock_version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint fan_voice_daily_reviews_unique unique (game_date, context_key, review_type),
  constraint fan_voice_daily_reviews_highlights_arr_chk check (jsonb_typeof(highlights) = 'array'),
  constraint fan_voice_daily_reviews_caution_notes_arr_chk check (jsonb_typeof(caution_notes) = 'array')
);

create index if not exists fan_voice_daily_reviews_game_date_idx
  on fan_voice_daily_reviews (game_date desc);

create index if not exists fan_voice_daily_reviews_status_idx
  on fan_voice_daily_reviews (generation_status, generated_at desc);

comment on column fan_voice_daily_reviews.review_type is
  'interim: during game, final: post game';

comment on column fan_voice_daily_reviews.highlights is
  'JSON array of {type, text}';

comment on column fan_voice_daily_reviews.caution_notes is
  'JSON array of {type, text}';

create table if not exists fan_voice_daily_opinions (
  id bigint generated always as identity primary key,
  review_id bigint not null references fan_voice_daily_reviews(id) on delete cascade,
  rank integer not null check (rank > 0),
  cluster_key text not null,
  opinion_title text not null,
  representative_message text not null,
  mention_count integer not null default 0,
  reaction_sum integer not null default 0,
  score numeric not null default 0,
  sentiment_hint text check (sentiment_hint in ('positive', 'negative', 'neutral', 'mixed')),
  primary_player_id uuid references players(id) on delete set null,
  evidence_message_ids uuid[] not null default '{}',
  evidence_count integer not null default 0,
  created_at timestamptz not null default now(),
  constraint fan_voice_daily_opinions_unique unique (review_id, rank)
);

create index if not exists fan_voice_daily_opinions_review_id_idx
  on fan_voice_daily_opinions (review_id, rank);

create index if not exists fan_voice_daily_opinions_cluster_key_idx
  on fan_voice_daily_opinions (cluster_key);

comment on column fan_voice_daily_opinions.cluster_key is
  'cluster key like c1, c2, outlier_<message_id>';

comment on column fan_voice_daily_opinions.score is
  'Computed score: mention_count * 0.7 + reaction_sum * 0.3';

create table if not exists fan_voice_daily_emotion_ranking (
  id bigint generated always as identity primary key,
  game_date date not null,
  context_key text not null default 'home:today',
  source_scope text not null check (source_scope in ('today', 'latest_fallback')),
  emotion_tag text not null,
  score numeric not null default 0,
  mention_count integer not null default 0,
  reaction_sum integer not null default 0,
  rank integer not null check (rank > 0),
  created_at timestamptz not null default now(),
  constraint fan_voice_daily_emotion_ranking_unique unique (game_date, context_key, emotion_tag)
);

create index if not exists fan_voice_daily_emotion_ranking_game_date_idx
  on fan_voice_daily_emotion_ranking (game_date desc, rank);

comment on column fan_voice_daily_emotion_ranking.score is
  'Formula: mention_count + ln(1 + reaction_sum)';

create table if not exists fan_voice_daily_player_ranking (
  id bigint generated always as identity primary key,
  game_date date not null,
  context_key text not null default 'home:today',
  source_scope text not null check (source_scope in ('today', 'latest_fallback')),
  player_id uuid not null references players(id) on delete cascade,
  score numeric not null default 0,
  mention_count integer not null default 0,
  reaction_sum integer not null default 0,
  rank integer not null check (rank > 0),
  sentiment_distribution jsonb not null default '{"positive":0,"neutral":0,"negative":0}'::jsonb,
  created_at timestamptz not null default now(),
  constraint fan_voice_daily_player_ranking_unique unique (game_date, context_key, player_id),
  constraint fan_voice_daily_player_ranking_sentiment_obj_chk check (jsonb_typeof(sentiment_distribution) = 'object')
);

create index if not exists fan_voice_daily_player_ranking_game_date_idx
  on fan_voice_daily_player_ranking (game_date desc, rank);

create index if not exists fan_voice_daily_player_ranking_player_idx
  on fan_voice_daily_player_ranking (player_id, game_date desc);

comment on column fan_voice_daily_player_ranking.score is
  'Formula: mention_count + 0.2 * reaction_sum';

comment on column fan_voice_daily_player_ranking.sentiment_distribution is
  'JSON object with positive/neutral/negative counts';

alter table fan_voice_messages
  add column if not exists normalized_message text,
  add column if not exists primary_player_id uuid references players(id) on delete set null,
  add column if not exists quality_score numeric default 1.0,
  add column if not exists is_duplicate boolean default false;

alter table fan_voice_messages
  drop constraint if exists fan_voice_messages_quality_score_range_chk;

alter table fan_voice_messages
  add constraint fan_voice_messages_quality_score_range_chk
  check (quality_score is null or (quality_score >= 0 and quality_score <= 1));

create index if not exists fan_voice_messages_game_date_status_idx
  on fan_voice_messages (game_date, status, created_at desc)
  where status = 'visible' and is_duplicate = false;

create index if not exists fan_voice_messages_context_game_idx
  on fan_voice_messages (context_type, context_id, game_date, created_at desc)
  where status = 'visible';

create index if not exists fan_voice_messages_primary_player_idx
  on fan_voice_messages (primary_player_id, game_date, created_at desc)
  where primary_player_id is not null;

create index if not exists fan_voice_messages_normalized_gin_idx
  on fan_voice_messages using gin (to_tsvector('simple', normalized_message))
  where normalized_message is not null;

comment on column fan_voice_messages.normalized_message is
  'Normalized text for clustering and duplicate detection';

comment on column fan_voice_messages.quality_score is
  'Quality score range [0,1]';

create table if not exists fan_voice_player_mentions (
  id bigint generated always as identity primary key,
  message_id uuid not null references fan_voice_messages(id) on delete cascade,
  game_date date not null,
  player_id uuid not null references players(id) on delete cascade,
  source text not null check (source in ('explicit', 'alias_match', 'context_inference')),
  confidence numeric default 1.0 check (confidence between 0 and 1),
  matched_text text,
  created_at timestamptz not null default now(),
  constraint fan_voice_player_mentions_unique unique (message_id, player_id)
);

create index if not exists fan_voice_player_mentions_game_idx
  on fan_voice_player_mentions (game_date, player_id);

create index if not exists fan_voice_player_mentions_message_idx
  on fan_voice_player_mentions (message_id);

comment on column fan_voice_player_mentions.source is
  'explicit|alias_match|context_inference';

create materialized view if not exists fan_voice_daily_message_stats as
select
  game_date,
  context_type,
  context_id,
  count(*) as total_messages,
  count(distinct session_id) as unique_users,
  count(distinct primary_player_id) filter (where primary_player_id is not null) as mentioned_players,
  avg(quality_score) as avg_quality,
  coalesce(sum(reaction_count), 0) as total_reactions,
  count(*) filter (where emotion_tag is not null) as messages_with_emotion
from fan_voice_messages
where status = 'visible' and coalesce(is_duplicate, false) = false
group by game_date, context_type, context_id;

create unique index if not exists fan_voice_daily_message_stats_unique_idx
  on fan_voice_daily_message_stats (game_date, context_type, context_id);

comment on materialized view fan_voice_daily_message_stats is
  'Daily cached stats for fan voice review generation';
