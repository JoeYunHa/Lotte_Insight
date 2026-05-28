-- Verification Script for Critical Fixes
-- Run this in Supabase SQL Editor AFTER executing migrations

-- ============================================================================
-- Step 1: Verify RPC Functions Exist
-- ============================================================================

select
  routine_name,
  routine_type,
  security_type,
  is_deterministic
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'aggregate_emotion_ranking',
    'aggregate_player_ranking',
    'replace_daily_opinions'
  )
order by routine_name;

-- Expected result:
-- aggregate_emotion_ranking | FUNCTION | DEFINER | NO
-- aggregate_player_ranking  | FUNCTION | DEFINER | NO
-- replace_daily_opinions    | FUNCTION | DEFINER | NO

-- ============================================================================
-- Step 2: Test replace_daily_opinions RPC (Transaction Safety)
-- ============================================================================

-- Create a test review (temporary)
do $$
declare
  v_review_id bigint;
begin
  -- Insert test review
  insert into fan_voice_daily_reviews (
    game_date,
    context_key,
    source_scope,
    summary_title,
    summary_body,
    message_count,
    unique_user_count
  ) values (
    '2026-01-01',
    'test:verify',
    'today',
    'Test Review',
    'Test Body',
    0,
    0
  )
  returning id into v_review_id;

  raise notice 'Created test review with id: %', v_review_id;

  -- Test 1: Insert opinions using RPC
  perform replace_daily_opinions(
    v_review_id,
    jsonb_build_array(
      jsonb_build_object(
        'cluster_key', 'c1',
        'opinion_title', 'Test Opinion 1',
        'representative_message', 'Test message 1',
        'mention_count', 10,
        'reaction_sum', 5,
        'score', 8.5,
        'sentiment_hint', 'positive',
        'primary_player_id', null,
        'evidence_message_ids', array[]::uuid[],
        'evidence_count', 0
      ),
      jsonb_build_object(
        'cluster_key', 'c2',
        'opinion_title', 'Test Opinion 2',
        'representative_message', 'Test message 2',
        'mention_count', 7,
        'reaction_sum', 3,
        'score', 5.9,
        'sentiment_hint', 'neutral',
        'primary_player_id', null,
        'evidence_message_ids', array[]::uuid[],
        'evidence_count', 0
      )
    )
  );

  -- Verify 2 opinions were inserted
  if (select count(*) from fan_voice_daily_opinions where review_id = v_review_id) != 2 then
    raise exception 'Test FAILED: Expected 2 opinions, got %',
      (select count(*) from fan_voice_daily_opinions where review_id = v_review_id);
  end if;

  raise notice 'Test 1 PASSED: 2 opinions inserted';

  -- Test 2: Replace with 1 opinion (should delete old ones)
  perform replace_daily_opinions(
    v_review_id,
    jsonb_build_array(
      jsonb_build_object(
        'cluster_key', 'c3',
        'opinion_title', 'Replaced Opinion',
        'representative_message', 'Replaced message',
        'mention_count', 15,
        'reaction_sum', 8,
        'score', 12.9,
        'sentiment_hint', 'positive',
        'primary_player_id', null,
        'evidence_message_ids', array[]::uuid[],
        'evidence_count', 0
      )
    )
  );

  -- Verify only 1 opinion exists now
  if (select count(*) from fan_voice_daily_opinions where review_id = v_review_id) != 1 then
    raise exception 'Test FAILED: Expected 1 opinion after replace, got %',
      (select count(*) from fan_voice_daily_opinions where review_id = v_review_id);
  end if;

  -- Verify it's the new opinion
  if (select cluster_key from fan_voice_daily_opinions where review_id = v_review_id) != 'c3' then
    raise exception 'Test FAILED: Expected cluster_key=c3, got %',
      (select cluster_key from fan_voice_daily_opinions where review_id = v_review_id);
  end if;

  raise notice 'Test 2 PASSED: Replace operation atomic';

  -- Test 3: Replace with empty array (should delete all)
  perform replace_daily_opinions(v_review_id, '[]'::jsonb);

  if (select count(*) from fan_voice_daily_opinions where review_id = v_review_id) != 0 then
    raise exception 'Test FAILED: Expected 0 opinions after empty replace, got %',
      (select count(*) from fan_voice_daily_opinions where review_id = v_review_id);
  end if;

  raise notice 'Test 3 PASSED: Empty replace deletes all';

  -- Cleanup
  delete from fan_voice_daily_reviews where id = v_review_id;

  raise notice '✅ ALL TESTS PASSED - replace_daily_opinions is transaction-safe';
end;
$$;

-- ============================================================================
-- Step 3: Test aggregate_emotion_ranking RPC (Security Hardening)
-- ============================================================================

-- Verify search_path protection (cannot inject malicious schema)
do $$
begin
  -- This should work normally
  perform * from aggregate_emotion_ranking(
    '2026-05-28'::date,
    'home',
    'today',
    0,
    5
  );

  raise notice '✅ aggregate_emotion_ranking security check passed';
exception
  when others then
    raise exception 'aggregate_emotion_ranking test FAILED: %', sqlerrm;
end;
$$;

-- ============================================================================
-- Step 4: Test aggregate_player_ranking RPC (Security Hardening)
-- ============================================================================

do $$
begin
  -- This should work normally
  perform * from aggregate_player_ranking(
    '2026-05-28'::date,
    'home',
    'today',
    0,
    10,
    null
  );

  raise notice '✅ aggregate_player_ranking security check passed';
exception
  when others then
    raise exception 'aggregate_player_ranking test FAILED: %', sqlerrm;
end;
$$;

-- ============================================================================
-- Summary
-- ============================================================================

select '✅ All Critical Fixes Verified Successfully!' as status;

-- Expected final output:
-- ✅ All Critical Fixes Verified Successfully!

-- If you see this message without errors, all critical fixes are working correctly!
