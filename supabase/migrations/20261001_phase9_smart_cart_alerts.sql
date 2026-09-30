create or replace function guard_smart_cart_customer_update()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    -- Restrict only ordinary authenticated customers.
    -- Trusted service_role/postgres/internal DB execution is allowed.
    if current_setting('role', true) = 'authenticated'
       and not is_staff()
    then

        if new.status is distinct from old.status then
            if old.status in ('triggered', 'completed') then
                raise exception
                    'Customers cannot change the status of a % Smart Cart rule',
                    old.status;
            end if;

            if new.status in ('triggered', 'completed') then
                raise exception
                    'Customers cannot set Smart Cart status to %',
                    new.status;
            end if;
        end if;

        if new.customer_id is distinct from old.customer_id
           or new.variant_id is distinct from old.variant_id
        then
            raise exception
                'Cannot change ownership/variant of an existing Smart Cart rule';
        end if;

        if new.triggered_at is distinct from old.triggered_at
           or new.last_evaluated_at is distinct from old.last_evaluated_at
        then
            raise exception
                'Cannot modify system-managed Smart Cart timestamps';
        end if;

        if old.status in ('triggered', 'completed') then
            if new.branch_id is distinct from old.branch_id
               or new.quantity is distinct from old.quantity
               or new.target_price is distinct from old.target_price
               or new.min_discount_percentage
                    is distinct from old.min_discount_percentage
               or new.authorization_mode
                    is distinct from old.authorization_mode
            then
                raise exception
                    'Cannot modify the parameters of a % Smart Cart rule',
                    old.status;
            end if;
        end if;
    end if;

    return new;
end;
$$;


create or replace function guard_alert_customer_update()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    -- Restrict only ordinary authenticated customers.
    -- Trusted service_role/postgres/internal DB execution is allowed.
    if current_setting('role', true) = 'authenticated'
       and not is_staff()
    then

        if new.customer_id is distinct from old.customer_id then
            raise exception
                'Cannot change ownership of an alert';
        end if;

        if new.triggered_at is distinct from old.triggered_at then
            raise exception
                'Alert trigger timestamp is system-managed';
        end if;

        if old.triggered_at is not null then
            raise exception
                'A triggered alert is immutable; create a new alert instead';
        end if;
    end if;

    return new;
end;
$$;

create or replace function evaluate_alerts_for_variant(
    p_variant_id uuid,
    p_event_type retail_event_type,
    p_price numeric,
    p_event_id uuid default null
)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
    a record;
    v_matched_type text;
    n int := 0;
begin
    v_matched_type := case p_event_type
        when 'price_changed' then 'price_drop'
        when 'restocked' then 'restock'
        when 'sale_started' then 'sale'
        else null
    end;

    if v_matched_type is null then
        return 0;
    end if;

    for a in
        select *
        from alerts
        where variant_id = p_variant_id
          and is_active = true
          and alert_type = v_matched_type
          and (
              alert_type <> 'price_drop'
              or target_price is null
              or (
                  p_price is not null
                  and p_price <= target_price
              )
          )
        for update
    loop
        update alerts
        set
            is_active = false,
            triggered_at = now()
        where id = a.id;

        perform create_notification(
            a.customer_id,
            (
                case a.alert_type
                    when 'price_drop'
                        then 'price_drop'
                    when 'restock'
                        then 'restock'
                    else 'sale'
                end
            )::notification_type,
            initcap(
                replace(
                    a.alert_type,
                    '_',
                    ' '
                )
            ) || ' alert',
            'A product on your alert list now matches your condition.',
            jsonb_build_object(
                'alert_id', a.id,
                'variant_id', p_variant_id,
                'price', p_price,
                'retail_event_id', p_event_id
            )
        );

        n := n + 1;
    end loop;

    return n;
end;
$$;