-- 실행 완료(2026-05-28)
create or replace function increment_fan_session_write_count(p_session_id bigint)
returns void
language sql
as $$
  update fan_sessions
  set write_count = write_count + 1
  where id = p_session_id;
$$;

create or replace function apply_fan_voice_reaction(
  p_message_id uuid,
  p_session_id bigint,
  p_reaction_type text
)
returns integer
language plpgsql
as $$
declare
  inserted_count integer;
  out_count integer;
begin
  insert into fan_voice_reactions (message_id, session_id, reaction_type)
  values (p_message_id, p_session_id, p_reaction_type)
  on conflict (message_id, session_id, reaction_type) do nothing;

  get diagnostics inserted_count = row_count;

  if inserted_count > 0 then
    update fan_voice_messages
    set reaction_count = reaction_count + 1
    where id = p_message_id
    returning reaction_count into out_count;
    return coalesce(out_count, 0);
  end if;

  select reaction_count into out_count
  from fan_voice_messages
  where id = p_message_id;
  return coalesce(out_count, 0);
end;
$$;

create or replace function apply_fan_voice_report(
  p_message_id uuid,
  p_session_id bigint,
  p_reason text
)
returns integer
language plpgsql
as $$
declare
  inserted_count integer;
  out_count integer;
begin
  insert into fan_voice_reports (message_id, session_id, reason)
  values (p_message_id, p_session_id, p_reason)
  on conflict (message_id, session_id) do nothing;

  get diagnostics inserted_count = row_count;

  if inserted_count > 0 then
    update fan_voice_messages
    set
      report_count = report_count + 1,
      status = case
        when report_count + 1 >= 5 then 'hidden'
        when report_count + 1 >= 3 and status = 'visible' then 'flagged'
        else status
      end
    where id = p_message_id
    returning report_count into out_count;
    return coalesce(out_count, 0);
  end if;

  select report_count into out_count
  from fan_voice_messages
  where id = p_message_id;
  return coalesce(out_count, 0);
end;
$$;
