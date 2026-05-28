-- Fan Voice Opinion Review v2 aggregation RPCs
-- 실행 완료(2026-05-28)

create or replace function aggregate_emotion_ranking(
  p_game_date date,
  p_context_type text,
  p_context_id text,
  p_min_mentions integer default 0,
  p_limit integer default 5
)
returns table (
  emotion_tag text,
  mention_count integer,
  reaction_sum integer,
  score numeric
)
language plpgsql
security definer
stable
as $$
begin
  -- Security: prevent schema injection attacks via search_path manipulation
  set local search_path = public, pg_temp;

  return query
  select
    m.emotion_tag,
    count(*)::int as mention_count,
    coalesce(sum(m.reaction_count), 0)::int as reaction_sum,
    -- Score formula: mention_count + ln(1 + reaction_sum)
    -- Python reference: backend/services/scoring.py::emotion_score()
    (count(*) + ln(1 + coalesce(sum(m.reaction_count), 0)))::numeric as score
  from fan_voice_messages m
  where m.game_date = p_game_date
    and m.context_type = p_context_type
    and m.context_id = p_context_id
    and m.status = 'visible'
    and coalesce(m.is_duplicate, false) = false
    and m.emotion_tag is not null
  group by m.emotion_tag
  having count(*) >= greatest(0, p_min_mentions)
  order by score desc
  limit greatest(1, least(100, p_limit));
end;
$$;

create or replace function aggregate_player_ranking(
  p_game_date date,
  p_context_type text,
  p_context_id text,
  p_min_mentions integer default 0,
  p_limit integer default 10,
  p_sentiment_filter text default null
)
returns table (
  player_id uuid,
  player_name text,
  player_position text,
  mention_count integer,
  reaction_sum integer,
  score numeric,
  sentiment_distribution jsonb
)
language plpgsql
security definer
stable
as $$
begin
  -- Security: prevent schema injection attacks via search_path manipulation
  set local search_path = public, pg_temp;

  return query
  with player_mentions_agg as (
    select
      m.player_id,
      count(*)::int as mention_count,
      coalesce(sum(msg.reaction_count), 0)::int as reaction_sum,
      -- Score formula: mention_count + 0.2 * reaction_sum
      -- Python reference: backend/services/scoring.py::player_score()
      (count(*) + 0.2 * coalesce(sum(msg.reaction_count), 0))::numeric as score,
      jsonb_build_object(
        'positive', count(*) filter (where msg.emotion_tag in ('excited', 'hopeful', 'proud')),
        'neutral', count(*) filter (where msg.emotion_tag in ('curious', 'calm') or msg.emotion_tag is null),
        'negative', count(*) filter (where msg.emotion_tag in ('frustrated', 'disappointed', 'angry'))
      ) as sentiment_distribution
    from fan_voice_player_mentions m
    join fan_voice_messages msg on msg.id = m.message_id
    where m.game_date = p_game_date
      and msg.context_type = p_context_type
      and msg.context_id = p_context_id
      and msg.status = 'visible'
      and coalesce(msg.is_duplicate, false) = false
    group by m.player_id
    having count(*) >= greatest(0, p_min_mentions)
  )
  select
    a.player_id,
    p.name as player_name,
    p.position as player_position,
    a.mention_count,
    a.reaction_sum,
    a.score,
    a.sentiment_distribution
  from player_mentions_agg a
  join players p on p.id = a.player_id
  where (
    p_sentiment_filter is null
    or (p_sentiment_filter = 'positive' and (a.sentiment_distribution->>'positive')::int > (a.sentiment_distribution->>'negative')::int)
    or (p_sentiment_filter = 'negative' and (a.sentiment_distribution->>'negative')::int > (a.sentiment_distribution->>'positive')::int)
    or (
      p_sentiment_filter = 'neutral'
      and (a.sentiment_distribution->>'neutral')::int >= (a.sentiment_distribution->>'positive')::int
      and (a.sentiment_distribution->>'neutral')::int >= (a.sentiment_distribution->>'negative')::int
    )
  )
  order by a.score desc
  limit greatest(1, least(100, p_limit));
end;
$$;
