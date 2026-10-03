-- ============================================================================
-- PHASE 10: NOTIFICATIONS
-- Delivery claiming / completion RPCs (service_role only) + read helpers.
-- ============================================================================

-- Index for unread-count queries.
create index if not exists idx_notifications_unread
on notifications(customer_id)
where read_at is null;


-- Atomically claim a batch of deliverable rows (pending, or failed with
-- attempts remaining and backoff elapsed, or stuck 'processing').
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
    return query
    with candidates as (
        select d.id
        from notification_deliveries d
        where d.attempts < p_max_attempts
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


create or replace function complete_notification_delivery(
    p_delivery_id uuid
)
returns void
language sql
security definer
set search_path = public
as $$
    update notification_deliveries
    set status = 'sent',
        sent_at = now(),
        error_message = null
    where id = p_delivery_id;
$$;


create or replace function fail_notification_delivery(
    p_delivery_id uuid,
    p_error text
)
returns void
language sql
security definer
set search_path = public
as $$
    update notification_deliveries
    set status = 'failed',
        error_message = left(coalesce(p_error, 'unknown error'), 1000)
    where id = p_delivery_id;
$$;


create or replace function mark_notifications_read(
    p_customer_id uuid,
    p_notification_ids uuid[] default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer;
begin
    update notifications
    set read_at = now()
    where customer_id = p_customer_id
      and read_at is null
      and (p_notification_ids is null or id = any(p_notification_ids));

    get diagnostics v_count = row_count;
    return v_count;
end;
$$;


revoke all on function claim_notification_deliveries(integer, integer, integer, integer) from public, anon, authenticated;
revoke all on function complete_notification_delivery(uuid) from public, anon, authenticated;
revoke all on function fail_notification_delivery(uuid, text) from public, anon, authenticated;
revoke all on function mark_notifications_read(uuid, uuid[]) from public, anon, authenticated;

grant execute on function claim_notification_deliveries(integer, integer, integer, integer) to service_role;
grant execute on function complete_notification_delivery(uuid) to service_role;
grant execute on function fail_notification_delivery(uuid, text) to service_role;
grant execute on function mark_notifications_read(uuid, uuid[]) to service_role;
