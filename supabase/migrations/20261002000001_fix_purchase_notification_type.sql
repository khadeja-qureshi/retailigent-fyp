CREATE OR REPLACE FUNCTION public.execute_mock_purchase(
    p_customer_id uuid,
    p_variant_id uuid,
    p_branch_id uuid,
    p_quantity integer,
    p_idempotency_key text,
    p_smart_cart_rule_id uuid DEFAULT NULL::uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
declare
    v_existing purchase_attempts%rowtype;
    v_rule smart_cart_rules%rowtype;
    v_customer profiles%rowtype;

    v_price numeric;
    v_regular_price numeric;
    v_discount numeric;
    v_total numeric;

    v_order_id uuid;
    v_attempt_id uuid;
    v_product_snapshot jsonb;
begin
    if p_quantity <= 0 then
        return jsonb_build_object(
            'success', false,
            'order_id', null,
            'purchase_attempt_id', null,
            'reason_code', 'invalid_quantity',
            'reason', 'Quantity must be greater than zero'
        );
    end if;

    if p_idempotency_key is null
       or btrim(p_idempotency_key) = '' then

        return jsonb_build_object(
            'success', false,
            'order_id', null,
            'purchase_attempt_id', null,
            'reason_code', 'invalid_idempotency_key',
            'reason', 'Idempotency key is required'
        );
    end if;

    select *
    into v_existing
    from purchase_attempts
    where idempotency_key = p_idempotency_key
    for update;

    if found then

        if v_existing.customer_id is distinct from p_customer_id
           or v_existing.variant_id is distinct from p_variant_id
           or v_existing.branch_id is distinct from p_branch_id
           or v_existing.quantity is distinct from p_quantity
           or v_existing.smart_cart_rule_id is distinct from p_smart_cart_rule_id then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', v_existing.id,
                'reason_code', 'idempotency_key_reused_with_different_request',
                'reason', 'The idempotency key was already used for a different purchase request'
            );
        end if;

        if v_existing.status = 'completed'
           and v_existing.order_id is not null then

            return jsonb_build_object(
                'success', true,
                'order_id', v_existing.order_id,
                'purchase_attempt_id', v_existing.id,
                'reason_code', 'already_completed',
                'reason', 'Purchase was already completed'
            );
        end if;

        if v_existing.status in ('started', 'validated') then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', v_existing.id,
                'reason_code', 'attempt_in_progress',
                'reason', 'Purchase attempt is already in progress'
            );
        end if;

    end if;

    select *
    into v_customer
    from profiles
    where id = p_customer_id
    for update;

    if not found
       or not v_customer.is_active then

        return jsonb_build_object(
            'success', false,
            'order_id', null,
            'purchase_attempt_id', null,
            'reason_code', 'customer_inactive',
            'reason', 'Customer account is not active'
        );
    end if;

    if not exists (
        select 1
        from branches
        where id = p_branch_id
          and is_active = true
    ) then

        return jsonb_build_object(
            'success', false,
            'order_id', null,
            'purchase_attempt_id', null,
            'reason_code', 'branch_inactive',
            'reason', 'Selected branch is not active'
        );
    end if;

    if p_smart_cart_rule_id is not null then

        select *
        into v_rule
        from smart_cart_rules
        where id = p_smart_cart_rule_id
        for update;

        if not found then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_not_found',
                'reason', 'Smart Cart rule was not found'
            );
        end if;

        if v_rule.customer_id <> p_customer_id then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_ownership_mismatch',
                'reason', 'Smart Cart rule does not belong to this customer'
            );
        end if;

        if v_rule.variant_id <> p_variant_id then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_variant_mismatch',
                'reason', 'Smart Cart rule does not match the purchase variant'
            );
        end if;

        if v_rule.status <> 'triggered' then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_not_triggered',
                'reason', 'Smart Cart rule is no longer triggered'
            );
        end if;

        if v_rule.authorization_mode <> 'auto_buy' then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_not_auto_buy',
                'reason', 'Smart Cart rule is not configured for Auto Buy'
            );
        end if;

        if p_quantity <> v_rule.quantity then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_quantity_mismatch',
                'reason', 'Purchase quantity does not match Smart Cart rule quantity'
            );
        end if;

        if v_rule.branch_id is not null
           and v_rule.branch_id <> p_branch_id then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_branch_mismatch',
                'reason', 'Purchase branch does not match Smart Cart rule branch'
            );
        end if;

        v_price := get_effective_variant_price(p_variant_id);

        if v_price is null then

            update smart_cart_rules
            set status = 'active',
                triggered_at = null,
                last_evaluated_at = now()
            where id = v_rule.id
              and status = 'triggered';

            insert into smart_cart_events (
                smart_cart_rule_id,
                retail_event_id,
                event_type,
                condition_snapshot,
                matched,
                action_taken
            )
            values (
                v_rule.id,
                null,
                'auto_buy_recheck',
                jsonb_build_object(
                    'reason', 'current_price_unavailable'
                ),
                false,
                'none'
            );

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_condition_stale',
                'reason', 'Current product price is no longer available',
                'smart_cart_rule_id', v_rule.id
            );
        end if;

        select coalesce(v.price, p.base_price)
        into v_regular_price
        from product_variants v
        join products p
          on p.id = v.product_id
        where v.id = p_variant_id;

        if v_regular_price is null then

            update smart_cart_rules
            set status = 'active',
                triggered_at = null,
                last_evaluated_at = now()
            where id = v_rule.id
              and status = 'triggered';

            insert into smart_cart_events (
                smart_cart_rule_id,
                retail_event_id,
                event_type,
                condition_snapshot,
                matched,
                action_taken
            )
            values (
                v_rule.id,
                null,
                'auto_buy_recheck',
                jsonb_build_object(
                    'reason', 'regular_price_unavailable',
                    'current_price', v_price
                ),
                false,
                'none'
            );

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_condition_stale',
                'reason', 'Current regular price is unavailable',
                'smart_cart_rule_id', v_rule.id
            );
        end if;

        v_discount :=
            case
                when v_regular_price > 0 then
                    ((v_regular_price - v_price) / v_regular_price) * 100
                else
                    0
            end;

        if v_rule.target_price is not null
           and v_price > v_rule.target_price then

            update smart_cart_rules
            set status = 'active',
                triggered_at = null,
                last_evaluated_at = now()
            where id = v_rule.id
              and status = 'triggered';

            insert into smart_cart_events (
                smart_cart_rule_id,
                retail_event_id,
                event_type,
                condition_snapshot,
                matched,
                action_taken
            )
            values (
                v_rule.id,
                null,
                'auto_buy_recheck',
                jsonb_build_object(
                    'price', v_price,
                    'regular_price', v_regular_price,
                    'discount_percentage', v_discount,
                    'target_price', v_rule.target_price,
                    'min_discount_percentage', v_rule.min_discount_percentage,
                    'reason', 'target_price_no_longer_satisfied'
                ),
                false,
                'none'
            );

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_condition_stale',
                'reason', 'Smart Cart target price is no longer satisfied',
                'smart_cart_rule_id', v_rule.id,
                'current_price', v_price,
                'target_price', v_rule.target_price,
                'discount_percentage', v_discount
            );
        end if;

        if v_rule.min_discount_percentage is not null
           and v_discount < v_rule.min_discount_percentage then

            update smart_cart_rules
            set status = 'active',
                triggered_at = null,
                last_evaluated_at = now()
            where id = v_rule.id
              and status = 'triggered';

            insert into smart_cart_events (
                smart_cart_rule_id,
                retail_event_id,
                event_type,
                condition_snapshot,
                matched,
                action_taken
            )
            values (
                v_rule.id,
                null,
                'auto_buy_recheck',
                jsonb_build_object(
                    'price', v_price,
                    'regular_price', v_regular_price,
                    'discount_percentage', v_discount,
                    'target_price', v_rule.target_price,
                    'min_discount_percentage', v_rule.min_discount_percentage,
                    'reason', 'min_discount_no_longer_satisfied'
                ),
                false,
                'none'
            );

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'smart_cart_condition_stale',
                'reason', 'Smart Cart minimum discount is no longer satisfied',
                'smart_cart_rule_id', v_rule.id,
                'current_price', v_price,
                'discount_percentage', v_discount,
                'min_discount_percentage', v_rule.min_discount_percentage
            );
        end if;

    else

        v_price := get_effective_variant_price(p_variant_id);

        if v_price is null then

            return jsonb_build_object(
                'success', false,
                'order_id', null,
                'purchase_attempt_id', null,
                'reason_code', 'variant_unavailable',
                'reason', 'Product variant is unavailable'
            );
        end if;

    end if;

    select jsonb_build_object(
        'product_id', p.id,
        'product_name', p.name,
        'variant_id', v.id,
        'variant_sku', v.sku,
        'price', v_price,
        'color_id', v.color_id,
        'size_id', v.size_id,
        'attributes', v.attributes
    )
    into v_product_snapshot
    from product_variants v
    join products p
      on p.id = v.product_id
    where v.id = p_variant_id;

    insert into purchase_attempts(
        customer_id,
        smart_cart_rule_id,
        variant_id,
        branch_id,
        quantity,
        status,
        validation_snapshot,
        idempotency_key
    )
    values(
        p_customer_id,
        p_smart_cart_rule_id,
        p_variant_id,
        p_branch_id,
        p_quantity,
        'started',
        jsonb_build_object(
            'price', v_price,
            'product_snapshot', v_product_snapshot
        ),
        p_idempotency_key
    )
    on conflict(idempotency_key) do nothing
    returning id
    into v_attempt_id;

    if v_attempt_id is null then

        select *
        into v_existing
        from purchase_attempts
        where idempotency_key = p_idempotency_key
        for update;

        if found then

            if v_existing.customer_id is distinct from p_customer_id
               or v_existing.variant_id is distinct from p_variant_id
               or v_existing.branch_id is distinct from p_branch_id
               or v_existing.quantity is distinct from p_quantity
               or v_existing.smart_cart_rule_id is distinct from p_smart_cart_rule_id then

                return jsonb_build_object(
                    'success', false,
                    'order_id', null,
                    'purchase_attempt_id', v_existing.id,
                    'reason_code', 'idempotency_key_reused_with_different_request',
                    'reason', 'The idempotency key was already used for a different purchase request'
                );
            end if;

            if v_existing.status = 'completed'
               and v_existing.order_id is not null then

                return jsonb_build_object(
                    'success', true,
                    'order_id', v_existing.order_id,
                    'purchase_attempt_id', v_existing.id,
                    'reason_code', 'already_completed',
                    'reason', 'Purchase was already completed'
                );
            end if;

            if v_existing.status in ('started', 'validated') then

                return jsonb_build_object(
                    'success', false,
                    'order_id', null,
                    'purchase_attempt_id', v_existing.id,
                    'reason_code', 'attempt_in_progress',
                    'reason', 'Purchase attempt is already in progress'
                );
            end if;

            v_attempt_id := v_existing.id;

            update purchase_attempts
            set status = 'started',
                customer_id = p_customer_id,
                smart_cart_rule_id = p_smart_cart_rule_id,
                variant_id = p_variant_id,
                branch_id = p_branch_id,
                quantity = p_quantity,
                validation_snapshot = jsonb_build_object(
                    'price', v_price,
                    'product_snapshot', v_product_snapshot
                ),
                failure_reason = null,
                order_id = null,
                completed_at = null
            where id = v_attempt_id;

        else

            insert into purchase_attempts(
                customer_id,
                smart_cart_rule_id,
                variant_id,
                branch_id,
                quantity,
                status,
                validation_snapshot,
                idempotency_key
            )
            values(
                p_customer_id,
                p_smart_cart_rule_id,
                p_variant_id,
                p_branch_id,
                p_quantity,
                'started',
                jsonb_build_object(
                    'price', v_price,
                    'product_snapshot', v_product_snapshot
                ),
                p_idempotency_key
            )
            returning id
            into v_attempt_id;

        end if;

    end if;

    begin

        perform adjust_inventory(
            p_variant_id,
            p_branch_id,
            -p_quantity,
            0,
            'sale',
            'purchase_attempt',
            v_attempt_id,
            'Mock Retailigent purchase',
            jsonb_build_object(
                'customer_id', p_customer_id
            )
        );

    exception when others then

        update purchase_attempts
        set status = 'failed',
            failure_reason = sqlerrm,
            validation_snapshot =
                validation_snapshot ||
                jsonb_build_object(
                    'failure', sqlerrm
                )
        where id = v_attempt_id;

        insert into audit_logs(
            actor_user_id,
            actor_type,
            action,
            entity_type,
            entity_id,
            metadata
        )
        values(
            p_customer_id,
            'system',
            'purchase_failed',
            'purchase_attempt',
            v_attempt_id,
            jsonb_build_object(
                'variant_id', p_variant_id,
                'branch_id', p_branch_id,
                'quantity', p_quantity,
                'reason', sqlerrm
            )
        );

        if p_smart_cart_rule_id is not null then

            update smart_cart_rules
            set status = 'active',
                triggered_at = null,
                last_evaluated_at = now()
            where id = p_smart_cart_rule_id
              and status = 'triggered';

            insert into smart_cart_events (
                smart_cart_rule_id,
                retail_event_id,
                event_type,
                condition_snapshot,
                matched,
                action_taken
            )
            values (
                p_smart_cart_rule_id,
                null,
                'auto_buy_failed',
                jsonb_build_object(
                    'variant_id', p_variant_id,
                    'branch_id', p_branch_id,
                    'quantity', p_quantity,
                    'reason', sqlerrm
                ),
                false,
                'purchase_failed'
            );

        end if;

        return jsonb_build_object(
            'success', false,
            'order_id', null,
            'purchase_attempt_id', v_attempt_id,
            'reason_code', 'inventory_adjustment_failed',
            'reason', sqlerrm
        );

    end;

    update purchase_attempts
    set status = 'validated'
    where id = v_attempt_id;

    v_total := v_price * p_quantity;

    insert into orders(
        customer_id,
        branch_id,
        status,
        subtotal,
        discount,
        total,
        currency,
        source
    )
    values(
        p_customer_id,
        p_branch_id,
        'confirmed',
        v_total,
        0,
        v_total,
        'PKR',
        'retailigent_smart_cart'
    )
    returning id
    into v_order_id;

    insert into order_items(
        order_id,
        variant_id,
        quantity,
        unit_price,
        line_total,
        product_snapshot
    )
    values(
        v_order_id,
        p_variant_id,
        p_quantity,
        v_price,
        v_total,
        v_product_snapshot
    );

    insert into payments(
        order_id,
        customer_id,
        amount,
        status,
        provider,
        provider_reference
    )
    values(
        v_order_id,
        p_customer_id,
        v_total,
        'paid',
        'mock',
        'MOCK-' || v_order_id::text
    );

    update purchase_attempts
    set status = 'completed',
        order_id = v_order_id,
        completed_at = now()
    where id = v_attempt_id;

    if p_smart_cart_rule_id is not null then

        update smart_cart_rules
        set status = 'completed'
        where id = p_smart_cart_rule_id
          and status = 'triggered';

        insert into smart_cart_events (
            smart_cart_rule_id,
            retail_event_id,
            event_type,
            condition_snapshot,
            matched,
            action_taken
        )
        values (
            p_smart_cart_rule_id,
            null,
            'auto_buy_completed',
            jsonb_build_object(
                'price', v_price,
                'quantity', p_quantity,
                'total', v_total,
                'order_id', v_order_id
            ),
            true,
            'purchase_completed'
        );

    end if;

    perform create_notification(
        p_customer_id,
        'purchase',
        'Purchase completed',
        'Your Retailigent Smart Cart purchase has been completed.',
        jsonb_build_object(
            'order_id', v_order_id,
            'purchase_attempt_id', v_attempt_id
        )
    );

    insert into audit_logs(
        actor_user_id,
        actor_type,
        action,
        entity_type,
        entity_id,
        metadata
    )
    values(
        p_customer_id,
        'system',
        'purchase_completed',
        'order',
        v_order_id,
        jsonb_build_object(
            'purchase_attempt_id', v_attempt_id,
            'variant_id', p_variant_id,
            'branch_id', p_branch_id,
            'quantity', p_quantity,
            'total', v_total,
            'smart_cart_rule_id', p_smart_cart_rule_id
        )
    );

    return jsonb_build_object(
        'success', true,
        'order_id', v_order_id,
        'purchase_attempt_id', v_attempt_id,
        'reason_code', 'purchase_completed',
        'reason', 'Mock purchase completed successfully',
        'total', v_total
    );

end;
$function$;