-- ============================================================================
-- RETAILIGENT
-- PHASE 12 / LOGICAL MIGRATION 0008
-- Cross-Conversation Customer Memory
--
-- The memory foundation was already present in the fresh-install master
-- schema. This additive migration makes Phase 12 explicit in migration
-- history and safely assures the required objects on existing deployments.
-- ============================================================================


-- ============================================================================
-- 1. MEMORY TYPE
-- ============================================================================

do $$
begin
    create type customer_memory_type as enum (
        'product_interest',
        'occasion_context',
        'communication_style',
        'fabric_or_style_note',
        'other'
    );
exception
    when duplicate_object then
        null;
end
$$;


-- ============================================================================
-- 2. CUSTOMER MEMORY TABLE
-- ============================================================================

create table if not exists customer_memory (
    id uuid primary key default gen_random_uuid(),

    customer_id uuid not null
        references profiles(id)
        on delete cascade,

    memory_type customer_memory_type not null,

    memory_key text not null
        check (
            btrim(memory_key) <> ''
        ),

    memory_value jsonb not null,

    confidence numeric(5,4)
        not null
        default 1.0
        check (
            confidence between 0 and 1
        ),

    source_conversation_id uuid
        references conversations(id)
        on delete set null,

    is_active boolean
        not null
        default true,

    last_confirmed_at timestamptz
        not null
        default now(),

    created_at timestamptz
        not null
        default now(),

    updated_at timestamptz
        not null
        default now(),

    unique (
        customer_id,
        memory_key
    )
);


create index if not exists
    idx_customer_memory_active
on customer_memory(
    customer_id,
    is_active,
    last_confirmed_at desc
);


create index if not exists
    idx_customer_memory_source
on customer_memory(
    source_conversation_id
)
where source_conversation_id
    is not null;


-- ============================================================================
-- 3. UPDATED_AT TRIGGER
-- ============================================================================

drop trigger if exists
    trg_customer_memory_updated_at
on customer_memory;


create trigger
    trg_customer_memory_updated_at
before update
on customer_memory
for each row
execute function set_updated_at();


-- ============================================================================
-- 4. ROW LEVEL SECURITY
-- ============================================================================

alter table customer_memory
enable row level security;


drop policy if exists
    own_customer_memory
on customer_memory;


create policy
    own_customer_memory
on customer_memory
for select
to authenticated
using (
    customer_id = auth.uid()
);


drop policy if exists
    delete_own_customer_memory
on customer_memory;


create policy
    delete_own_customer_memory
on customer_memory
for delete
to authenticated
using (
    customer_id = auth.uid()
);


-- ============================================================================
-- 5. MEMORY UPSERT RPC
-- ============================================================================

create or replace function
upsert_customer_memory(
    p_customer_id uuid,
    p_memory_type customer_memory_type,
    p_memory_key text,
    p_memory_value jsonb,
    p_confidence numeric default 1.0,
    p_source_conversation_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_id uuid;
begin
    if (
        p_memory_key is null
        or
        btrim(
            p_memory_key
        ) = ''
    ) then
        raise exception
            'memory_key is required';
    end if;

    if (
        p_confidence is null
        or
        p_confidence < 0
        or
        p_confidence > 1
    ) then
        raise exception
            'confidence must be between 0 and 1';
    end if;

    if not exists (
        select 1
        from profiles
        where id = p_customer_id
          and is_active = true
    ) then
        raise exception
            'Customer account is not active';
    end if;

    if (
        p_source_conversation_id
        is not null
        and
        not exists (
            select 1
            from conversations
            where id =
                p_source_conversation_id
              and customer_id =
                p_customer_id
        )
    ) then
        raise exception
            'Source conversation does not belong to customer';
    end if;

    insert into customer_memory(
        customer_id,
        memory_type,
        memory_key,
        memory_value,
        confidence,
        source_conversation_id,
        is_active,
        last_confirmed_at
    )
    values(
        p_customer_id,
        p_memory_type,
        btrim(
            p_memory_key
        ),
        p_memory_value,
        p_confidence,
        p_source_conversation_id,
        true,
        now()
    )
    on conflict(
        customer_id,
        memory_key
    )
    do update
    set
        memory_type =
            excluded.memory_type,

        memory_value =
            excluded.memory_value,

        confidence =
            excluded.confidence,

        source_conversation_id =
            excluded.source_conversation_id,

        is_active =
            true,

        last_confirmed_at =
            now(),

        updated_at =
            now()

    returning id
    into v_id;

    return v_id;
end;
$$;


-- ============================================================================
-- 6. CONTEXT SNAPSHOT RPC
-- ============================================================================

create or replace function
get_customer_context_snapshot(
    p_customer_id uuid
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    v_snapshot jsonb;
begin
    if not exists (
        select 1
        from profiles
        where id = p_customer_id
    ) then
        return null;
    end if;

    select
        jsonb_build_object(
            'preferences',
            coalesce(
                (
                    select
                        to_jsonb(cp)
                        - 'customer_id'

                    from
                        customer_preferences
                        cp

                    where
                        cp.customer_id =
                        p_customer_id
                ),
                '{}'::jsonb
            ),

            'recent_orders',
            coalesce(
                (
                    select
                        jsonb_agg(
                            to_jsonb(o)
                            order by
                                o.created_at
                                desc
                        )

                    from (
                        select
                            id,
                            branch_id,
                            status,
                            subtotal,
                            discount,
                            total,
                            currency,
                            source,
                            created_at

                        from
                            orders

                        where
                            customer_id =
                            p_customer_id

                        order by
                            created_at desc

                        limit 5
                    ) o
                ),
                '[]'::jsonb
            ),

            'open_support_tickets',
            coalesce(
                (
                    select
                        jsonb_agg(
                            jsonb_build_object(
                                'id',
                                s.id,

                                'subject',
                                s.subject,

                                'status',
                                s.status,

                                'priority',
                                s.priority,

                                'sentiment',
                                s.sentiment,

                                'assigned_staff_id',
                                s.assigned_staff_id,

                                'created_at',
                                s.created_at,

                                'updated_at',
                                s.updated_at
                            )
                            order by
                                s.updated_at
                                desc
                        )

                    from
                        support_escalations
                        s

                    where
                        s.customer_id =
                        p_customer_id

                        and
                        s.status
                        not in (
                            'resolved',
                            'closed'
                        )
                ),
                '[]'::jsonb
            ),

            'active_smart_cart_rules',
            coalesce(
                (
                    select
                        jsonb_agg(
                            to_jsonb(sc)
                            order by
                                sc.created_at
                                desc
                        )

                    from
                        smart_cart_rules
                        sc

                    where
                        sc.customer_id =
                        p_customer_id

                        and
                        sc.status
                        in (
                            'active',
                            'triggered'
                        )
                ),
                '[]'::jsonb
            ),

            'active_alerts',
            coalesce(
                (
                    select
                        jsonb_agg(
                            to_jsonb(a)
                            order by
                                a.created_at
                                desc
                        )

                    from
                        alerts
                        a

                    where
                        a.customer_id =
                        p_customer_id

                        and
                        a.is_active =
                        true
                ),
                '[]'::jsonb
            ),

            'remembered_facts',
            coalesce(
                (
                    select
                        jsonb_agg(
                            jsonb_build_object(
                                'id',
                                m.id,

                                'memory_type',
                                m.memory_type,

                                'memory_key',
                                m.memory_key,

                                'memory_value',
                                m.memory_value,

                                'confidence',
                                m.confidence,

                                'effective_confidence',
                                case
                                    when
                                        m.last_confirmed_at
                                        <
                                        now()
                                        -
                                        interval '90 days'
                                    then
                                        greatest(
                                            0,
                                            m.confidence
                                            * 0.5
                                        )
                                    else
                                        m.confidence
                                end,

                                'is_stale',
                                (
                                    m.last_confirmed_at
                                    <
                                    now()
                                    -
                                    interval '90 days'
                                ),

                                'source_conversation_id',
                                m.source_conversation_id,

                                'last_confirmed_at',
                                m.last_confirmed_at,

                                'created_at',
                                m.created_at,

                                'updated_at',
                                m.updated_at
                            )
                            order by
                                case
                                    when
                                        m.last_confirmed_at
                                        <
                                        now()
                                        -
                                        interval '90 days'
                                    then
                                        m.confidence
                                        * 0.5
                                    else
                                        m.confidence
                                end
                                desc,

                                m.last_confirmed_at
                                desc
                        )

                    from (
                        select
                            *

                        from
                            customer_memory

                        where
                            customer_id =
                            p_customer_id

                            and
                            is_active =
                            true

                        order by
                            confidence desc,
                            last_confirmed_at
                            desc

                        limit 20
                    ) m
                ),
                '[]'::jsonb
            )
        )
    into
        v_snapshot;

    return
        v_snapshot;
end;
$$;


-- ============================================================================
-- 7. FUNCTION ACCESS
-- ============================================================================

revoke all
on function
upsert_customer_memory(
    uuid,
    customer_memory_type,
    text,
    jsonb,
    numeric,
    uuid
)
from public;


revoke all
on function
get_customer_context_snapshot(
    uuid
)
from public;


grant execute
on function
upsert_customer_memory(
    uuid,
    customer_memory_type,
    text,
    jsonb,
    numeric,
    uuid
)
to service_role;


grant execute
on function
get_customer_context_snapshot(
    uuid
)
to service_role;


-- ============================================================================
-- 8. MEMORY & CONTEXT AGENT REGISTRY
-- ============================================================================

insert into agent_registry(
    agent_key,
    display_name,
    description,
    agent_type
)
values(
    'memory_context',
    'Memory & Context Agent',
    (
        'Loads durable customer context at the start '
        'of a conversation and extracts/reconfirms '
        'privacy-controlled facts for future conversations.'
    ),
    'specialist'
)
on conflict(
    agent_key
)
do update
set
    display_name =
        excluded.display_name,

    description =
        excluded.description,

    agent_type =
        excluded.agent_type;