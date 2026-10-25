-- ============================================================================
-- PHASE 17: SCHEDULING & BACKGROUND WORKERS
--
-- Adds:
--   1. Explicit notification dead-letter status.
--   2. Service-role-only dead-letter RPC.
--   3. Supporting delivery queue index.
--
-- Existing Phase 10 RPCs already provide:
--   - atomic claiming
--   - exponential retry backoff
--   - stale processing recovery
--
-- Phase 17 completes the pipeline by giving permanently exhausted deliveries
-- an explicit dead_letter state.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. Add explicit dead-letter status
-- ---------------------------------------------------------------------------

alter type notification_delivery_status
add value if not exists 'dead_letter';


-- ---------------------------------------------------------------------------
-- 2. Mark one exhausted notification delivery as dead-lettered
-- ---------------------------------------------------------------------------

create or replace function mark_notification_delivery_dead_letter(
    p_delivery_id uuid,
    p_error text default null
)
returns void
language sql
security definer
set search_path = public
as $$
    update notification_deliveries
    set
        status = 'dead_letter',
        error_message = left(
            coalesce(
                p_error,
                'Maximum notification delivery attempts exhausted'
            ),
            1000
        )
    where id = p_delivery_id
      and status <> 'sent';
$$;


-- ---------------------------------------------------------------------------
-- 3. Security
-- ---------------------------------------------------------------------------

revoke all
on function mark_notification_delivery_dead_letter(uuid, text)
from public, anon, authenticated;

grant execute
on function mark_notification_delivery_dead_letter(uuid, text)
to service_role;


-- ---------------------------------------------------------------------------
-- 4. Queue lookup index
-- ---------------------------------------------------------------------------

create index if not exists
idx_notification_deliveries_worker_queue
on notification_deliveries(
    status,
    attempts,
    last_attempt_at,
    created_at
)
where status in (
    'pending',
    'failed',
    'processing'
);