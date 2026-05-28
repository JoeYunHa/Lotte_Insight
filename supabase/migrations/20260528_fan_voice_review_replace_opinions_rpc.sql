-- Replace daily opinions RPC (transaction-safe)
-- Fixes Critical Issue #1: Transaction safety for delete-then-insert pattern
-- 실행 완료(2026-05-28)

create or replace function replace_daily_opinions(
  p_review_id bigint,
  p_opinions jsonb  -- array of opinion objects
)
returns void
language plpgsql
security definer
as $$
begin
  -- Security: prevent schema injection attacks
  set local search_path = public, pg_temp;

  -- Delete existing opinions for this review
  delete from fan_voice_daily_opinions where review_id = p_review_id;

  -- Insert new opinions if provided
  if jsonb_array_length(p_opinions) > 0 then
    insert into fan_voice_daily_opinions (
      review_id,
      rank,
      cluster_key,
      opinion_title,
      representative_message,
      mention_count,
      reaction_sum,
      score,
      sentiment_hint,
      primary_player_id,
      evidence_message_ids,
      evidence_count
    )
    select
      p_review_id,
      (idx + 1)::int,
      (item->>'cluster_key')::text,
      (item->>'opinion_title')::text,
      (item->>'representative_message')::text,
      (item->>'mention_count')::int,
      (item->>'reaction_sum')::int,
      (item->>'score')::numeric,
      (item->>'sentiment_hint')::text,
      nullif(item->>'primary_player_id', '')::uuid,
      (
        select array_agg(elem::text::uuid)
        from jsonb_array_elements_text(item->'evidence_message_ids') elem
      ),
      (item->>'evidence_count')::int
    from jsonb_array_elements(p_opinions) with ordinality arr(item, idx);
  end if;
end;
$$;

comment on function replace_daily_opinions is
  'Atomically replace opinions for a review (transaction-safe delete+insert)';
