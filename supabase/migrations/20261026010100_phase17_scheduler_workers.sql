create or replace function public.mark_notification_delivery_dead_letter(
    p_delivery_id uuid,
    p_error text default null
)
returns void
language sql
security definer
set search_path = public
as $$
    update public.notification_deliveries
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


revoke all
on function public.mark_notification_delivery_dead_letter(
    uuid,
    text
)
from
    public,
    anon,
    authenticated;


grant execute
on function public.mark_notification_delivery_dead_letter(
    uuid,
    text
)
to service_role;


create index if not exists
idx_notification_deliveries_worker_queue

on public.notification_deliveries(
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