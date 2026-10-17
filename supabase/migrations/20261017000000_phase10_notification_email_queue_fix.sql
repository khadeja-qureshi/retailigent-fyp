create or replace function create_notification(
    p_customer_id uuid,
    p_type notification_type,
    p_title text,
    p_message text,
    p_metadata jsonb default '{}'::jsonb,
    p_email boolean default false
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_notification_id uuid;
    v_email_allowed boolean := false;
begin
    insert into notifications(
        customer_id,
        type,
        title,
        message,
        metadata
    )
    values(
        p_customer_id,
        p_type,
        p_title,
        p_message,
        coalesce(p_metadata, '{}'::jsonb)
    )
    returning id into v_notification_id;

    -- In-app is always queued.
    perform queue_notification_delivery(
        v_notification_id,
        'in_app'
    );

    -- Check customer email preference.
    select coalesce(
        (
            select cp.allow_email_notifications
            from customer_preferences cp
            where cp.customer_id = p_customer_id
        ),
        false
    )
    into v_email_allowed;

    -- Queue email for opted-in commerce notifications.
    if v_email_allowed
       and (
            p_email
            or p_type in (
                'price_drop'::notification_type,
                'restock'::notification_type,
                'sale'::notification_type,
                'smart_cart_match'::notification_type,
                'purchase'::notification_type
            )
       )
    then
        perform queue_notification_delivery(
            v_notification_id,
            'email'
        );
    end if;

    return v_notification_id;
end;
$$;


revoke all
on function create_notification(
    uuid,
    notification_type,
    text,
    text,
    jsonb,
    boolean
)
from public, anon, authenticated;


grant execute
on function create_notification(
    uuid,
    notification_type,
    text,
    text,
    jsonb,
    boolean
)
to service_role;