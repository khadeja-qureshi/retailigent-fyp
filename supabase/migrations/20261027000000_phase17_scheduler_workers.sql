-- ============================================================================
-- PHASE 17: SCHEDULING & BACKGROUND WORKERS
--
-- 1. job_runs: heartbeat table so every scheduler job reports its last run
--    (read by the admin jobs endpoint; staff can read it, clients cannot write).
-- 2. record_job_run(): upserts a job's heartbeat (service_role only).
-- 3. notification_deliveries dead-letter handling:
--      * dead_lettered_at marks a delivery that will never be retried
--      * claim_notification_deliveries(): never claims dead-lettered rows and
--        dead-letters rows stuck in 'processing' after the attempt limit
--      * fail_notification_delivery(): dead-letters on the last attempt or
--        immediately for permanent errors
--      * requeue_dead_letter_deliveries(): admin recovery (audited)
--
-- All new functions are service_role only (Phase 16 policy). Safe to re-run.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. job_runs
-- ----------------------------------------------------------------------------
create table if not exists job_runs (
    job_name             text primary key,
    interval_seconds     integer not null check (interval_seconds > 0),
    last_started_at      timestamptz,
    last_finished_at     timestamptz,
    last_success_at      timestamptz,
    last_status          text check (last_status in ('ok', 'failed')),
    last_error           text,
    last_duration_ms     integer,
    last_result          jsonb,
    run_count            bigint not null default 0,
    failure_count        bigint not null default 0,
    consecutive_failures integer not null default 0,
    updated_at           timestamptz not null default now()
);

alter table job_runs enable row level security;

drop policy if exists staff_read_job_runs on job_runs;
create policy staff_read_job_runs
on job_runs for select to authenticated
using (is_staff());

-- Supabase grants new tables to anon/authenticated by default (Phase 16 finding F3).
revoke all on job_runs from anon, authenticated;
grant select on job_runs to authenticated;
grant all on job_runs to service_role;


-- ----------------------------------------------------------------------------
-- 2. record_job_run
-- ----------------------------------------------------------------------------
-- Counters are passed as deltas so the scheduler can persist successes
-- periodically (not on every 2-second tick) without losing run counts.
create or replace function record_job_run(
    p_job                  text,
    p_interval_seconds     integer,
    p_ok                   boolean,
    p_error                text,
    p_duration_ms          integer,
    p_result               jsonb,
    p_started_at           timestamptz,
    p_runs_delta           bigint,
    p_failures_delta       bigint,
    p_consecutive_failures integer
)
returns void
language sql
security definer
set search_path = public
as $$
    insert into job_runs as j (
        job_name, interval_seconds, last_started_at, last_finished_at,
        last_success_at, last_status, last_error, last_duration_ms,
        last_result, run_count, failure_count, consecutive_failures, updated_at
    )
    values (
        p_job,
        greatest(p_interval_seconds, 1),
        p_started_at,
        now(),
        case when p_ok then now() else null end,
        case when p_ok then 'ok' else 'failed' end,
        case when p_ok then null else left(p_error, 1000) end,
        p_duration_ms,
        p_result,
        greatest(p_runs_delta, 0),
        greatest(p_failures_delta, 0),
        greatest(p_consecutive_failures, 0),
        now()
    )
    on conflict (job_name) do update
    set interval_seconds     = excluded.interval_seconds,
        last_started_at      = excluded.last_started_at,
        last_finished_at     = excluded.last_finished_at,
        last_success_at      = case when p_ok then now() else j.last_success_at end,
        last_status          = excluded.last_status,
        last_error           = excluded.last_error,
        last_duration_ms     = excluded.last_duration_ms,
        last_result          = excluded.last_result,
        run_count            = j.run_count + greatest(p_runs_delta, 0),
        failure_count        = j.failure_count + greatest(p_failures_delta, 0),
        consecutive_failures = greatest(p_consecutive_failures, 0),
        updated_at           = now();
$$;


-- ----------------------------------------------------------------------------
-- 3. Notification dead-letter handling
-- ----------------------------------------------------------------------------
alter table notification_deliveries
    add column if not exists dead_lettered_at timestamptz;

create index if not exists idx_notification_deliveries_dead
    on notification_deliveries(dead_lettered_at)
    where dead_lettered_at is not null;


create or replace function claim_notification_deliveries(
    p_limit integer default 20,
    p_max_attempts integer default 5,
    p_base_backoff_seconds integer default 30,
    p_stale_processing_seconds integer default 300
)
returns setof notification_deliveries
language plpgsql
security definer
set search_path = public
as $$
begin
    -- A worker that crashed mid-delivery leaves the row in 'processing'.
    -- Once it has used all its attempts it must not stay there forever.
    update notification_deliveries d
    set status = 'failed',
        dead_lettered_at = now(),
        error_message = coalesce(d.error_message, 'worker stopped before finishing')
    where d.status = 'processing'
      and d.dead_lettered_at is null
      and d.attempts >= p_max_attempts
      and d.last_attempt_at is not null
      and d.last_attempt_at + p_stale_processing_seconds * interval '1 second' <= now();

    return query
    with candidates as (
        select d.id
        from notification_deliveries d
        where d.dead_lettered_at is null
          and d.attempts < p_max_attempts
          and (
                d.status = 'pending'
             or (
                    d.status = 'failed'
                and d.last_attempt_at is not null
                and d.last_attempt_at
                    + (p_base_backoff_seconds * power(2, greatest(d.attempts - 1, 0))) * interval '1 second'
                    <= now()
                )
             or (
                    d.status = 'processing'
                and d.last_attempt_at is not null
                and d.last_attempt_at
                    + p_stale_processing_seconds * interval '1 second' <= now()
                )
          )
        order by d.created_at
        limit greatest(p_limit, 1)
        for update skip locked
    )
    update notification_deliveries d
    set status = 'processing',
        attempts = d.attempts + 1,
        last_attempt_at = now()
    from candidates c
    where d.id = c.id
    returning d.*;
end;
$$;


-- The old 2-argument version is replaced (avoid a confusing overload).
drop function if exists fail_notification_delivery(uuid, text);

create or replace function fail_notification_delivery(
    p_delivery_id uuid,
    p_error text,
    p_permanent boolean default false,
    p_max_attempts integer default 5
)
returns void
language sql
security definer
set search_path = public
as $$
    update notification_deliveries
    set status = 'failed',
        error_message = left(coalesce(p_error, 'unknown error'), 1000),
        dead_lettered_at = case
            when p_permanent or attempts >= p_max_attempts then now()
            else dead_lettered_at
        end
    where id = p_delivery_id;
$$;


-- Admin recovery: put dead-lettered deliveries back in the queue.
-- p_delivery_ids null = every dead-lettered delivery. Returns how many.
create or replace function requeue_dead_letter_deliveries(
    p_delivery_ids uuid[] default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer;
begin
    update notification_deliveries
    set status = 'pending',
        attempts = 0,
        dead_lettered_at = null,
        error_message = null,
        last_attempt_at = null
    where dead_lettered_at is not null
      and (p_delivery_ids is null or id = any(p_delivery_ids));

    get diagnostics v_count = row_count;

    if v_count > 0 then
        insert into audit_logs(
            actor_user_id, actor_type, action, entity_type, metadata
        )
        values (
            current_actor_id(),
            case when current_actor_id() is null then 'system' else 'staff' end,
            'notification_deliveries_requeued',
            'notification_deliveries',
            jsonb_build_object(
                'count', v_count,
                'scope', case when p_delivery_ids is null then 'all' else 'selected' end
            )
        );
    end if;

    return v_count;
end;
$$;


-- ----------------------------------------------------------------------------
-- Grants: service_role only (explicit, on top of Phase 16 default privileges)
-- ----------------------------------------------------------------------------
revoke all on function record_job_run(text, integer, boolean, text, integer, jsonb, timestamptz, bigint, bigint, integer)
    from public, anon, authenticated;
revoke all on function claim_notification_deliveries(integer, integer, integer, integer)
    from public, anon, authenticated;
revoke all on function fail_notification_delivery(uuid, text, boolean, integer)
    from public, anon, authenticated;
revoke all on function requeue_dead_letter_deliveries(uuid[])
    from public, anon, authenticated;

grant execute on function record_job_run(text, integer, boolean, text, integer, jsonb, timestamptz, bigint, bigint, integer)
    to service_role;
grant execute on function claim_notification_deliveries(integer, integer, integer, integer)
    to service_role;
grant execute on function fail_notification_delivery(uuid, text, boolean, integer)
    to service_role;
grant execute on function requeue_dead_letter_deliveries(uuid[])
    to service_role;
