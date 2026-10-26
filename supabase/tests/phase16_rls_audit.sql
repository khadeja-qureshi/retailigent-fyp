-- ============================================================================
-- PHASE 16: RLS / GRANTS / AUDIT TEST SUITE
--
-- Penetration-style checks run as real Postgres roles (anon / authenticated)
-- against every table and every function in `public`, plus audit coverage.
--
-- HOW TO RUN
--   * Supabase Dashboard -> SQL Editor -> paste the whole file -> Run, or
--   * psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/phase16_rls_audit.sql
--
-- SAFETY: everything runs inside ONE transaction that is ROLLED BACK at the
-- end. Fixtures (auth users, catalog rows, orders, ...) never persist.
-- Existing real data is never modified; real rows only matter because the
-- suite proves test customers cannot see them either.
--
-- RESULT: a final table of every check. Any failure aborts with a message
-- listing the failed checks. Silence on failure is impossible: the last
-- statement raises.
-- ============================================================================
begin;

create schema p16_test;

create table p16_test.results (
    n serial primary key,
    area text not null,
    label text not null,
    ok boolean not null,
    detail text
);

create table p16_test.ids (k text primary key, v uuid not null);


-- ---------------------------------------------------------------------------
-- Helpers (run as the migration role; they switch role INSIDE, then switch back)
-- ---------------------------------------------------------------------------
create function p16_test.id(p_key text) returns uuid
language sql stable as $$ select v from p16_test.ids where k = p_key $$;

create function p16_test.record(p_area text, p_label text, p_ok boolean, p_detail text default null)
returns void language sql as $$
    insert into p16_test.results(area, label, ok, detail) values (p_area, p_label, p_ok, p_detail)
$$;

create function p16_test.set_ctx(p_uid uuid, p_role text) returns void
language plpgsql as $$
begin
    perform set_config('request.jwt.claim.sub', coalesce(p_uid::text, ''), true);
    perform set_config('request.jwt.claim.role', p_role, true);
    perform set_config('request.jwt.claims',
        json_build_object('sub', p_uid, 'role', p_role)::text, true);
    perform set_config('role', p_role, true);
end $$;

create function p16_test.reset_ctx() returns void
language plpgsql as $$
begin
    execute 'reset role';
    perform set_config('request.jwt.claim.sub', '', true);
    perform set_config('request.jwt.claim.role', '', true);
    perform set_config('request.jwt.claims', '', true);
end $$;

-- scalar bigint query executed AS a role
create function p16_test.val_as(p_uid uuid, p_role text, p_sql text) returns bigint
language plpgsql as $$
declare v bigint;
begin
    begin
        perform p16_test.set_ctx(p_uid, p_role);
        execute p_sql into v;
    exception when others then
        execute 'reset role'; perform set_config('request.jwt.claim.sub','',true); perform set_config('request.jwt.claim.role','',true); perform set_config('request.jwt.claims','',true);
        return -1;      -- -1 = error (e.g. permission denied)
    end;
    execute 'reset role'; perform set_config('request.jwt.claim.sub','',true); perform set_config('request.jwt.claim.role','',true); perform set_config('request.jwt.claims','',true);
    return v;
end $$;

-- statement MUST be rejected with insufficient_privilege / RLS violation (42501)
create function p16_test.denied_as(p_area text, p_label text, p_uid uuid, p_role text, p_sql text)
returns void language plpgsql as $$
declare v_ok boolean := false; v_msg text;
begin
    begin
        perform p16_test.set_ctx(p_uid, p_role);
        execute p_sql;
        v_msg := 'statement SUCCEEDED but must be denied';
    exception
        when insufficient_privilege then v_ok := true; v_msg := 'denied (42501)';
        when others then v_msg := 'unexpected error ' || sqlstate || ': ' || sqlerrm;
    end;
    execute 'reset role'; perform set_config('request.jwt.claim.sub','',true); perform set_config('request.jwt.claim.role','',true); perform set_config('request.jwt.claims','',true);
    perform p16_test.record(p_area, p_label, v_ok, v_msg);
end $$;

-- statement MUST be rejected by SOMETHING: privilege/RLS (42501) or a guard trigger (P0001)
create function p16_test.blocked_as(p_area text, p_label text, p_uid uuid, p_role text, p_sql text)
returns void language plpgsql as $$
declare v_ok boolean := false; v_msg text;
begin
    begin
        perform p16_test.set_ctx(p_uid, p_role);
        execute p_sql;
        v_msg := 'statement SUCCEEDED but must be blocked';
    exception
        when insufficient_privilege or raise_exception then v_ok := true; v_msg := 'blocked: ' || sqlerrm;
        when others then v_msg := 'unexpected error ' || sqlstate || ': ' || sqlerrm;
    end;
    execute 'reset role'; perform set_config('request.jwt.claim.sub','',true); perform set_config('request.jwt.claim.role','',true); perform set_config('request.jwt.claims','',true);
    perform p16_test.record(p_area, p_label, v_ok, v_msg);
end $$;

-- statement runs but MUST affect zero rows (RLS silently filters) or be denied
create function p16_test.zero_rows_as(p_area text, p_label text, p_uid uuid, p_role text, p_sql text)
returns void language plpgsql as $$
declare v_ok boolean := false; v_msg text; v_rows bigint;
begin
    begin
        perform p16_test.set_ctx(p_uid, p_role);
        execute p_sql;
        get diagnostics v_rows = row_count;
        v_ok := (v_rows = 0);
        v_msg := v_rows || ' row(s) affected';
    exception
        when insufficient_privilege then v_ok := true; v_msg := 'denied (42501)';
        when others then v_msg := 'unexpected error ' || sqlstate || ': ' || sqlerrm;
    end;
    execute 'reset role'; perform set_config('request.jwt.claim.sub','',true); perform set_config('request.jwt.claim.role','',true); perform set_config('request.jwt.claims','',true);
    perform p16_test.record(p_area, p_label, v_ok, v_msg);
end $$;

-- statement MUST succeed and affect exactly p_expect rows (positive control)
create function p16_test.rows_as(p_area text, p_label text, p_uid uuid, p_role text, p_sql text, p_expect bigint)
returns void language plpgsql as $$
declare v_ok boolean := false; v_msg text; v_rows bigint;
begin
    begin
        perform p16_test.set_ctx(p_uid, p_role);
        execute p_sql;
        get diagnostics v_rows = row_count;
        v_ok := (v_rows = p_expect);
        v_msg := v_rows || ' row(s) affected, expected ' || p_expect;
    exception when others then
        v_msg := 'error ' || sqlstate || ': ' || sqlerrm;
    end;
    execute 'reset role'; perform set_config('request.jwt.claim.sub','',true); perform set_config('request.jwt.claim.role','',true); perform set_config('request.jwt.claims','',true);
    perform p16_test.record(p_area, p_label, v_ok, v_msg);
end $$;

create function p16_test.assert(p_area text, p_label text, p_ok boolean, p_detail text default null)
returns void language sql as $$ select p16_test.record(p_area, p_label, coalesce(p_ok, false), p_detail) $$;


-- ---------------------------------------------------------------------------
-- Fixtures
-- ---------------------------------------------------------------------------
do $$
declare
    a uuid := '00000000-0000-4000-8000-0000000000a1';   -- customer A
    b uuid := '00000000-0000-4000-8000-0000000000b2';   -- customer B
    s uuid := '00000000-0000-4000-8000-000000000051';   -- staff
    v_prod uuid; v_var uuid; v_branch uuid;
    c uuid; conv uuid; tkt uuid; ord uuid; rule uuid; cust uuid; rid uuid;
begin
    insert into p16_test.ids values ('A', a), ('B', b), ('S', s);

    insert into auth.users(id, email) values
        (a, 'p16-a@example.test'), (b, 'p16-b@example.test'), (s, 'p16-staff@example.test');
    -- handle_new_user() created profiles + 'customer' roles
    insert into user_roles(user_id, role) values (s, 'staff');

    insert into products(name, slug, base_price) values ('P16 Product', 'p16-product-' || gen_random_uuid(), 1000)
        returning id into v_prod;
    insert into product_variants(product_id, sku) values (v_prod, 'P16-' || gen_random_uuid())
        returning id into v_var;
    insert into branches(name, city) values ('P16 Branch', 'Testville') returning id into v_branch;
    insert into branch_inventory(branch_id, variant_id, on_hand_quantity) values (v_branch, v_var, 50);
    insert into p16_test.ids values ('VAR', v_var), ('BRANCH', v_branch);

    foreach cust in array array[a, b] loop
        insert into carts(customer_id) values (cust) returning id into c;
        insert into cart_items(cart_id, variant_id, quantity) values (c, v_var, 1);
        insert into wishlists(customer_id, variant_id) values (cust, v_var);
        insert into alerts(customer_id, variant_id, alert_type, target_price) values (cust, v_var, 'price_drop', 500);
        insert into smart_cart_rules(customer_id, variant_id, target_price) values (cust, v_var, 500) returning id into rule;
        insert into smart_cart_events(smart_cart_rule_id, event_type) values (rule, 'p16_test');
        insert into notifications(customer_id, type, title, message) values (cust, 'general', 'p16', 'p16');
        insert into customer_memory(customer_id, memory_type, memory_key, memory_value)
            values (cust, 'other', 'p16_key', '{"secret": true}'::jsonb);
        insert into customer_preferences(customer_id) values (cust) on conflict do nothing;
        insert into conversations(customer_id, title) values (cust, 'p16') returning id into conv;
        insert into messages(conversation_id, role, content) values (conv, 'user', 'p16 private message');
        insert into conversation_state(conversation_id, state) values (conv, '{}'::jsonb);
        insert into feedback(customer_id, feedback_type, message) values (cust, 'general', 'p16 feedback')
            returning id into rid;
        insert into p16_test.ids values ('FEEDBACK_' || left(cust::text, 0) || (case when cust = a then 'A' else 'B' end), rid);
        insert into support_escalations(customer_id, subject) values (cust, 'p16') returning id into tkt;
        insert into p16_test.ids values ('TICKET_' || (case when cust = a then 'A' else 'B' end), tkt);
        insert into support_ticket_messages(ticket_id, sender_type, message) values (tkt, 'customer', 'p16');
        insert into orders(customer_id) values (cust) returning id into ord;
        insert into order_items(order_id, variant_id, quantity, unit_price, line_total) values (ord, v_var, 1, 1000, 1000);
        insert into payments(order_id, customer_id, amount) values (ord, cust, 1000);
        insert into agent_runs(customer_id, root_agent_key, input_text) values (cust, 'p16', 'p16') returning id into rid;
        insert into agent_tasks(agent_run_id, agent_key, task_type) values (rid, 'p16', 'p16');
        insert into agent_tool_calls(agent_run_id, agent_key, tool_name) values (rid, 'p16', 'p16');
        perform create_reservation(cust, v_var, v_branch, 1, now() + interval '1 hour');
    end loop;
end $$;


-- ===========================================================================
-- 1. TABLE COVERAGE: every base table must be classified (new tables fail here)
-- ===========================================================================
create table p16_test.owned (tbl text primary key, pred text not null, staff_reads boolean not null);
-- pred: SQL predicate with %L for the customer id, evaluated by the test owner
insert into p16_test.owned values
 ('profiles',               'id = %L', true),
 ('user_roles',             'user_id = %L', true),
 ('customer_preferences',   'customer_id = %L', true),
 ('customer_memory',        'customer_id = %L', false),   -- staff must NOT read memory
 ('carts',                  'customer_id = %L', true),
 ('cart_items',             'cart_id in (select id from carts where customer_id = %L)', true),
 ('wishlists',              'customer_id = %L', true),
 ('alerts',                 'customer_id = %L', true),
 ('smart_cart_rules',       'customer_id = %L', true),
 ('smart_cart_events',      'smart_cart_rule_id in (select id from smart_cart_rules where customer_id = %L)', true),
 ('notifications',          'customer_id = %L', true),
 ('conversations',          'customer_id = %L', true),
 ('messages',               'conversation_id in (select id from conversations where customer_id = %L)', true),
 ('conversation_state',     'conversation_id in (select id from conversations where customer_id = %L)', true),
 ('feedback',               'customer_id = %L', true),
 ('support_escalations',    'customer_id = %L', true),
 ('support_ticket_messages','ticket_id in (select id from support_escalations where customer_id = %L)', true),
 ('orders',                 'customer_id = %L', true),
 ('order_items',            'order_id in (select id from orders where customer_id = %L)', true),
 ('payments',               'customer_id = %L', true),
 ('reservations',           'customer_id = %L', true),
 ('agent_runs',             'customer_id = %L', true),
 ('agent_tasks',            'agent_run_id in (select id from agent_runs where customer_id = %L)', true),
 ('agent_tool_calls',       'agent_run_id in (select id from agent_runs where customer_id = %L)', true);

create table p16_test.staff_only (tbl text primary key);
insert into p16_test.staff_only values
 ('audit_logs'), ('branch_inventory'), ('demand_signals'), ('inventory_movements'),
 ('notification_deliveries'), ('price_history'), ('promotions'), ('purchase_attempts'),
 ('retail_events'), ('agent_registry'), ('job_runs');

create table p16_test.catalog (tbl text primary key);   -- intentionally world-readable
insert into p16_test.catalog values
 ('branches'), ('categories'), ('colors'), ('sizes'), ('products'),
 ('product_variants'), ('product_images');

create table p16_test.service_only (tbl text primary key);  -- no client policy at all
insert into p16_test.service_only values ('product_embeddings');

do $$ begin perform p16_test.assert('coverage', 'every public table is classified in this suite: ' || c.relname,
    exists (select 1 from p16_test.owned where tbl = c.relname)
    or exists (select 1 from p16_test.staff_only where tbl = c.relname)
    or exists (select 1 from p16_test.catalog where tbl = c.relname)
    or exists (select 1 from p16_test.service_only where tbl = c.relname),
    'add this table to the classification lists at the top of the suite')
from pg_class c
where c.relnamespace = 'public'::regnamespace and c.relkind in ('r', 'p'); end $$;

do $$ begin perform p16_test.assert('coverage', 'RLS enabled: ' || c.relname, c.relrowsecurity)
from pg_class c where c.relnamespace = 'public'::regnamespace and c.relkind in ('r', 'p'); end $$;

do $$ begin perform p16_test.assert('coverage', 'view is security_invoker: ' || c.relname,
    coalesce(c.reloptions::text, '') ilike '%security_invoker=true%')
from pg_class c where c.relnamespace = 'public'::regnamespace and c.relkind = 'v'; end $$;


-- ===========================================================================
-- 2. CROSS-CUSTOMER READS  (customer A must never see customer B's data)
-- ===========================================================================
do $$
declare
    r record;
    a uuid := p16_test.id('A'); b uuid := p16_test.id('B'); s uuid := p16_test.id('S');
    owned_a bigint; owned_b bigint; seen_all bigint; seen_b bigint; seen_staff bigint;
begin
    for r in select * from p16_test.owned order by tbl loop
        execute format('select count(*) from public.%I where ' || r.pred, r.tbl, a) into owned_a;
        execute format('select count(*) from public.%I where ' || r.pred, r.tbl, b) into owned_b;

        perform p16_test.assert('read', 'fixture exists for ' || r.tbl || ' (positive control)',
            owned_a >= 1 and owned_b >= 1,
            case when owned_a >= 1 and owned_b >= 1 then null
                 else 'no seeded rows for A/B: this table is NOT really tested' end);

        seen_all := p16_test.val_as(a, 'authenticated', format('select count(*) from public.%I', r.tbl));
        seen_b   := p16_test.val_as(a, 'authenticated',
                        format('select count(*) from public.%I where ' || r.pred, r.tbl, b));

        perform p16_test.assert('read', 'A sees ONLY own rows in ' || r.tbl,
            seen_all = owned_a, format('A sees %s, owns %s', seen_all, owned_a));
        perform p16_test.assert('read', 'A sees ZERO of B''s rows in ' || r.tbl,
            seen_b = 0, format('A sees %s of B''s rows', seen_b));

        seen_all := p16_test.val_as(b, 'authenticated', format('select count(*) from public.%I', r.tbl));
        perform p16_test.assert('read', 'B sees ONLY own rows in ' || r.tbl,
            seen_all = owned_b, format('B sees %s, owns %s', seen_all, owned_b));

        -- staff visibility
        seen_staff := p16_test.val_as(s, 'authenticated',
                        format('select count(*) from public.%I where ' || r.pred, r.tbl, a));
        if r.staff_reads then
            perform p16_test.assert('read', 'staff CAN read customer rows in ' || r.tbl,
                seen_staff = owned_a, format('staff sees %s of %s', seen_staff, owned_a));
        else
            perform p16_test.assert('read', 'staff can NOT read customer rows in ' || r.tbl,
                seen_staff = 0, format('staff sees %s', seen_staff));
        end if;
    end loop;
end $$;

-- staff-only tables: non-staff sees nothing; staff sees everything
do $$
declare
    r record; a uuid := p16_test.id('A'); s uuid := p16_test.id('S');
    total bigint; seen_a bigint; seen_s bigint;
begin
    for r in select tbl from p16_test.staff_only order by tbl loop
        execute format('select count(*) from public.%I', r.tbl) into total;
        seen_a := p16_test.val_as(a, 'authenticated', format('select count(*) from public.%I', r.tbl));
        seen_s := p16_test.val_as(s, 'authenticated', format('select count(*) from public.%I', r.tbl));
        perform p16_test.assert('read', 'customer sees 0 rows in staff-only ' || r.tbl,
            seen_a = 0, format('customer sees %s of %s', seen_a, total));
        perform p16_test.assert('read', 'staff sees all rows in ' || r.tbl,
            seen_s = total, format('staff sees %s of %s', seen_s, total));
    end loop;
end $$;

-- service-only tables: no client role can read
do $$ begin perform p16_test.assert('read', 'no client access at all to ' || t.tbl || ' (authenticated)',
    p16_test.val_as(p16_test.id('A'), 'authenticated', format('select count(*) from public.%I', t.tbl)) in (0, -1))
from p16_test.service_only t; end $$;


-- ===========================================================================
-- 3. ANONYMOUS ACCESS
-- ===========================================================================
do $$
declare r record;
begin
    for r in
        select c.relname from pg_class c
        where c.relnamespace = 'public'::regnamespace and c.relkind in ('r','p','v')
          and c.relname not in (select tbl from p16_test.catalog)
        order by 1
    loop
        perform p16_test.denied_as('anon', 'anon cannot SELECT ' || r.relname, null, 'anon',
            format('select count(*) from public.%I', r.relname));
    end loop;

    for r in select c.relname from pg_class c where c.relnamespace = 'public'::regnamespace and c.relkind in ('r','p') loop
        perform p16_test.assert('anon', 'anon has NO write privileges on ' || r.relname,
            not (has_table_privilege('anon', 'public.' || quote_ident(r.relname), 'INSERT')
              or has_table_privilege('anon', 'public.' || quote_ident(r.relname), 'UPDATE')
              or has_table_privilege('anon', 'public.' || quote_ident(r.relname), 'DELETE')
              or has_table_privilege('anon', 'public.' || quote_ident(r.relname), 'TRUNCATE')));
    end loop;
end $$;


-- ===========================================================================
-- 4. CROSS-CUSTOMER WRITES + PRIVILEGE ESCALATION
-- ===========================================================================
do $$
declare
    a uuid := p16_test.id('A'); b uuid := p16_test.id('B'); s uuid := p16_test.id('S');
    v uuid := p16_test.id('VAR'); br uuid := p16_test.id('BRANCH');
    b_conv uuid; b_cart uuid;
begin
    select id into b_conv from conversations where customer_id = b limit 1;
    select id into b_cart from carts where customer_id = b limit 1;

    -- A tries to modify B's rows: RLS must filter to 0 rows
    perform p16_test.zero_rows_as('write', 'A cannot UPDATE B''s cart', a, 'authenticated',
        format('update carts set status = ''abandoned'' where customer_id = %L', b));
    perform p16_test.zero_rows_as('write', 'A cannot DELETE B''s wishlist', a, 'authenticated',
        format('delete from wishlists where customer_id = %L', b));
    perform p16_test.zero_rows_as('write', 'A cannot UPDATE B''s profile', a, 'authenticated',
        format('update profiles set full_name = ''hacked'' where id = %L', b));
    perform p16_test.zero_rows_as('write', 'A cannot UPDATE B''s alert', a, 'authenticated',
        format('update alerts set target_price = 1 where customer_id = %L', b));
    perform p16_test.zero_rows_as('write', 'A cannot UPDATE B''s smart-cart rule', a, 'authenticated',
        format('update smart_cart_rules set status = ''cancelled'' where customer_id = %L', b));
    perform p16_test.zero_rows_as('write', 'A cannot DELETE B''s customer_memory', a, 'authenticated',
        format('delete from customer_memory where customer_id = %L', b));
    perform p16_test.zero_rows_as('write', 'A cannot UPDATE B''s preferences', a, 'authenticated',
        format('update customer_preferences set budget_max = 1 where customer_id = %L', b));
    perform p16_test.zero_rows_as('write', 'A cannot UPDATE B''s cart items', a, 'authenticated',
        format('update cart_items set quantity = 99 where cart_id = %L', b_cart));
    perform p16_test.zero_rows_as('write', 'A cannot DELETE B''s conversation', a, 'authenticated',
        format('delete from conversations where customer_id = %L', b));

    -- A tries to INSERT rows owned by B / hand rows to B: RLS WITH CHECK -> 42501
    perform p16_test.denied_as('write', 'A cannot INSERT wishlist for B', a, 'authenticated',
        format('insert into wishlists(customer_id, variant_id) values (%L, %L)', b, v));
    perform p16_test.denied_as('write', 'A cannot INSERT cart for B', a, 'authenticated',
        format('insert into carts(customer_id) values (%L)', b));
    perform p16_test.denied_as('write', 'A cannot INSERT alert for B', a, 'authenticated',
        format('insert into alerts(customer_id, variant_id, alert_type) values (%L, %L, ''price_drop'')', b, v));
    perform p16_test.denied_as('write', 'A cannot INSERT feedback for B', a, 'authenticated',
        format('insert into feedback(customer_id, feedback_type, message) values (%L, ''general'', ''x'')', b));
    perform p16_test.denied_as('write', 'A cannot INSERT support ticket for B', a, 'authenticated',
        format('insert into support_escalations(customer_id, subject) values (%L, ''x'')', b));
    perform p16_test.denied_as('write', 'A cannot INSERT message into B''s conversation', a, 'authenticated',
        format('insert into messages(conversation_id, role, content) values (%L, ''user'', ''x'')', b_conv));
    perform p16_test.denied_as('write', 'A cannot INSERT preferences for B', a, 'authenticated',
        format('insert into customer_preferences(customer_id) values (%L)', b));
    perform p16_test.blocked_as('write', 'A cannot hand own cart to B (ownership transfer)', a, 'authenticated',
        format('update carts set customer_id = %L where customer_id = %L', b, a));
    perform p16_test.blocked_as('write', 'A cannot hand own alert to B (ownership transfer)', a, 'authenticated',
        format('update alerts set customer_id = %L where customer_id = %L', b, a));

    -- Tables with no client write policy at all
    perform p16_test.denied_as('escalation', 'customer cannot INSERT notifications', a, 'authenticated',
        format('insert into notifications(customer_id, type, title, message) values (%L, ''general'', ''x'', ''x'')', a));
    perform p16_test.denied_as('escalation', 'customer cannot UPDATE notifications (read flag)', a, 'authenticated',
        format('update notifications set read_at = now() where customer_id = %L', a));
    perform p16_test.denied_as('escalation', 'customer cannot INSERT orders', a, 'authenticated',
        format('insert into orders(customer_id) values (%L)', a));
    perform p16_test.denied_as('escalation', 'customer cannot UPDATE orders', a, 'authenticated',
        format('update orders set status = ''completed'' where customer_id = %L', a));
    perform p16_test.denied_as('escalation', 'customer cannot INSERT payments', a, 'authenticated',
        format('insert into payments(order_id, customer_id, amount) select id, customer_id, 1 from orders where customer_id = %L limit 1', a));
    perform p16_test.denied_as('escalation', 'customer cannot INSERT reservations', a, 'authenticated',
        format('insert into reservations(customer_id, variant_id, branch_id, quantity, expires_at) values (%L, %L, %L, 1, now() + interval ''1 hour'')', a, v, br));
    perform p16_test.denied_as('escalation', 'customer cannot INSERT customer_memory (service-written only)', a, 'authenticated',
        format('insert into customer_memory(customer_id, memory_type, memory_key, memory_value) values (%L, ''other'', ''k'', ''{}''::jsonb)', a));
    perform p16_test.denied_as('escalation', 'customer cannot UPDATE customer_memory', a, 'authenticated',
        format('update customer_memory set memory_value = ''{}''::jsonb where customer_id = %L', a));
    perform p16_test.denied_as('escalation', 'customer cannot grant self admin role', a, 'authenticated',
        format('insert into user_roles(user_id, role) values (%L, ''admin'')', a));
    perform p16_test.denied_as('escalation', 'customer cannot change own role', a, 'authenticated',
        format('update user_roles set role = ''admin'' where user_id = %L', a));
    perform p16_test.denied_as('escalation', 'customer cannot delete own role row', a, 'authenticated',
        format('delete from user_roles where user_id = %L', a));
    perform p16_test.denied_as('escalation', 'customer cannot INSERT promotions', a, 'authenticated',
        'insert into promotions(name, discount_type, discount_value, starts_at) values (''x'', ''percentage'', 99, now())');
    perform p16_test.denied_as('escalation', 'customer cannot UPDATE stock', a, 'authenticated',
        'update branch_inventory set on_hand_quantity = 0');
    perform p16_test.denied_as('escalation', 'customer cannot UPDATE prices', a, 'authenticated',
        'update products set base_price = 1');
    perform p16_test.denied_as('escalation', 'customer cannot INSERT retail_events', a, 'authenticated',
        'insert into retail_events(event_type) values (''price_changed'')');
    perform p16_test.denied_as('escalation', 'customer cannot TRUNCATE a customer table', a, 'authenticated',
        'truncate table carts');

    -- audit_logs: nobody on the client side can touch it
    perform p16_test.denied_as('audit', 'customer cannot INSERT audit_logs', a, 'authenticated',
        'insert into audit_logs(actor_type, action, entity_type) values (''user'', ''x'', ''x'')');
    perform p16_test.denied_as('audit', 'customer cannot DELETE audit_logs', a, 'authenticated', 'delete from audit_logs');
    perform p16_test.denied_as('audit', 'customer cannot UPDATE audit_logs', a, 'authenticated', 'update audit_logs set action = ''x''');
    perform p16_test.denied_as('audit', 'staff cannot INSERT audit_logs', s, 'authenticated',
        'insert into audit_logs(actor_type, action, entity_type) values (''staff'', ''x'', ''x'')');
    perform p16_test.denied_as('audit', 'staff cannot DELETE audit_logs', s, 'authenticated', 'delete from audit_logs');
    perform p16_test.denied_as('audit', 'staff cannot UPDATE audit_logs', s, 'authenticated', 'update audit_logs set action = ''x''');

    -- staff are read-only on the client side: writes go through the backend
    perform p16_test.denied_as('escalation', 'staff cannot write promotions directly', s, 'authenticated',
        'insert into promotions(name, discount_type, discount_value, starts_at) values (''x'', ''percentage'', 99, now())');
    perform p16_test.denied_as('escalation', 'staff cannot write stock directly', s, 'authenticated',
        'update branch_inventory set on_hand_quantity = 0');
    perform p16_test.denied_as('escalation', 'staff cannot grant roles directly', s, 'authenticated',
        format('insert into user_roles(user_id, role) values (%L, ''admin'')', s));

    -- positive controls: legitimate own-data writes still work after the grants tightening
    perform p16_test.rows_as('positive', 'A can UPDATE own profile (guard trigger still fires)', a, 'authenticated',
        format('update profiles set full_name = ''P16 A'' where id = %L', a), 1);
    perform p16_test.rows_as('positive', 'A can INSERT own wishlist row', a, 'authenticated',
        format('insert into wishlists(customer_id, variant_id) select %L, id from product_variants where id <> %L limit 1', a, v), 0);
    perform p16_test.rows_as('positive', 'A can DELETE own wishlist row', a, 'authenticated',
        format('delete from wishlists where customer_id = %L', a), 1);
    perform p16_test.rows_as('positive', 'A can DELETE own customer_memory (forget)', a, 'authenticated',
        format('delete from customer_memory where customer_id = %L', a), 1);
    perform p16_test.rows_as('positive', 'A can UPDATE own preferences', a, 'authenticated',
        format('update customer_preferences set budget_max = 5000 where customer_id = %L', a), 1);
end $$;


-- ===========================================================================
-- 5. FUNCTION GRANTS  (every mutating RPC is service_role-only)
-- ===========================================================================
create table p16_test.fn_allow (sig text primary key);
insert into p16_test.fn_allow values
 ('is_staff()'), ('get_stock_status(integer)'),
 ('get_effective_variant_price(uuid)'), ('get_effective_variant_prices(uuid[])');

do $$ begin perform p16_test.assert('functions', 'anon cannot EXECUTE ' || p.oid::regprocedure::text,
    not has_function_privilege('anon', p.oid, 'execute'))
from pg_proc p
where p.pronamespace = 'public'::regnamespace and p.prokind in ('f','p')
  and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e'); end $$;

do $$ begin perform p16_test.assert('functions',
    'authenticated EXECUTE only if allowlisted read-only: ' || p.oid::regprocedure::text,
    has_function_privilege('authenticated', p.oid, 'execute')
        = exists (select 1 from p16_test.fn_allow f where f.sig = p.oid::regprocedure::text))
from pg_proc p
where p.pronamespace = 'public'::regnamespace and p.prokind in ('f','p')
  and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e'); end $$;

do $$ begin perform p16_test.assert('functions', 'service_role CAN execute ' || p.oid::regprocedure::text,
    has_function_privilege('service_role', p.oid, 'execute'))
from pg_proc p
where p.pronamespace = 'public'::regnamespace and p.prokind in ('f','p')
  and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e'); end $$;

-- real calls: every non-trigger, non-allowlisted function must be refused for customer AND anon
do $$
declare
    r record; call_sql text;
    a uuid := p16_test.id('A');
begin
    for r in
        select p.oid, p.oid::regprocedure::text as sig,
               (select coalesce(string_agg('null::' ||
                         case when tn.nspname <> 'pg_catalog' then quote_ident(tn.nspname) || '.' else '' end ||
                         format_type(u.t, null), ', ' order by u.ord), '')
                  from unnest(p.proargtypes::oid[]) with ordinality as u(t, ord)
                  join pg_type ty on ty.oid = u.t
                  join pg_namespace tn on tn.oid = ty.typnamespace) as args,
               format('public.%I', p.proname) as fname
        from pg_proc p
        where p.pronamespace = 'public'::regnamespace and p.prokind = 'f'
          and p.prorettype <> 'trigger'::regtype
          and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')
          and not exists (select 1 from p16_test.fn_allow f where f.sig = p.oid::regprocedure::text)
    loop
        call_sql := format('select %s(%s)', r.fname, r.args);
        perform p16_test.denied_as('functions', 'customer call refused: ' || r.sig, a, 'authenticated', call_sql);
        perform p16_test.denied_as('functions', 'anon call refused: ' || r.sig, null, 'anon', call_sql);
    end loop;
end $$;

-- the headline attacks, spelled out with REAL arguments
do $$ begin perform p16_test.denied_as('functions', 'customer cannot adjust stock', p16_test.id('A'), 'authenticated',
    format('select adjust_inventory(%L, %L, 100, 0, ''adjustment'', ''x'', null, ''x'', ''{}''::jsonb)', p16_test.id('VAR'), p16_test.id('BRANCH'))); end $$;
do $$ begin perform p16_test.denied_as('functions', 'customer cannot buy as someone else', p16_test.id('A'), 'authenticated',
    format('select execute_mock_purchase(%L, %L, %L, 1, ''p16-attack'', null)', p16_test.id('B'), p16_test.id('VAR'), p16_test.id('BRANCH'))); end $$;
do $$ begin perform p16_test.denied_as('functions', 'customer cannot reserve as someone else', p16_test.id('A'), 'authenticated',
    format('select create_reservation(%L, %L, %L, 1, now() + interval ''1 hour'')', p16_test.id('B'), p16_test.id('VAR'), p16_test.id('BRANCH'))); end $$;
do $$ begin perform p16_test.denied_as('functions', 'customer cannot read B''s memory snapshot', p16_test.id('A'), 'authenticated',
    format('select get_customer_context_snapshot(%L)', p16_test.id('B'))); end $$;
do $$ begin perform p16_test.denied_as('functions', 'customer cannot forge notifications', p16_test.id('A'), 'authenticated',
    format('select create_notification(%L, ''general'', ''x'', ''x'', ''{}''::jsonb, false)', p16_test.id('B'))); end $$;
do $$ begin perform p16_test.denied_as('functions', 'customer cannot write memory', p16_test.id('A'), 'authenticated',
    format('select upsert_customer_memory(%L, ''other'', ''k'', ''{}''::jsonb, 1, null)', p16_test.id('B'))); end $$;


-- ===========================================================================
-- 6. AUDIT COVERAGE  (run as the migration owner = same effect as service_role)
-- ===========================================================================
do $$
declare
    a uuid := p16_test.id('A'); s uuid := p16_test.id('S'); b uuid := p16_test.id('B');
    v uuid := p16_test.id('VAR'); br uuid := p16_test.id('BRANCH');
    n0 bigint; n1 bigint; rid uuid; promo uuid; row audit_logs; res uuid; ord jsonb;
begin
    -- 6.1 role changes -------------------------------------------------------
    perform set_config('app.actor_user_id', s::text, true);
    insert into user_roles(user_id, role) values (b, 'manager') returning id into rid;
    select * into row from audit_logs where entity_type = 'user_roles' and entity_id = rid and action = 'role_granted';
    perform p16_test.assert('audit', 'role grant is audited with actor', row.id is not null and row.actor_user_id = s and row.actor_type = 'staff',
        format('actor=%s type=%s', row.actor_user_id, row.actor_type));
    perform p16_test.assert('audit', 'role grant records after_data', row.after_data ->> 'role' = 'manager');

    update user_roles set role = 'staff' where id = rid;
    select * into row from audit_logs where entity_id = rid and action = 'role_updated';
    perform p16_test.assert('audit', 'role update is audited with before/after',
        row.before_data ->> 'role' = 'manager' and row.after_data ->> 'role' = 'staff');

    delete from user_roles where id = rid;
    select * into row from audit_logs where entity_id = rid and action = 'role_revoked';
    perform p16_test.assert('audit', 'role revoke is audited', row.id is not null and row.before_data ->> 'role' = 'staff');

    -- 6.2 unattributed changes are labelled 'system', not 'staff' ------------
    perform set_config('app.actor_user_id', '', true);
    insert into user_roles(user_id, role) values (b, 'manager') returning id into rid;
    select * into row from audit_logs where entity_id = rid and action = 'role_granted';
    perform p16_test.assert('audit', 'unattributed role change is labelled system with null actor',
        row.actor_type = 'system' and row.actor_user_id is null, format('type=%s actor=%s', row.actor_type, row.actor_user_id));
    delete from user_roles where id = rid;

    -- 6.3 actor attribution rules -------------------------------------------
    perform set_config('request.jwt.claims', '{"role":"service_role"}', true);
    perform set_config('request.headers', json_build_object('x-actor-user-id', s)::text, true);
    perform p16_test.assert('audit', 'service_role + x-actor-user-id header attributes the staff member',
        current_actor_id() = s);

    perform set_config('request.headers', json_build_object('x-actor-user-id', gen_random_uuid())::text, true);
    perform p16_test.assert('audit', 'header naming a non-existent profile is ignored (no FK failure)',
        current_actor_id() is null);

    perform set_config('request.headers', json_build_object('x-actor-user-id', 'not-a-uuid')::text, true);
    perform p16_test.assert('audit', 'garbage header is ignored', current_actor_id() is null);

    perform set_config('request.jwt.claims', json_build_object('role', 'authenticated', 'sub', a)::text, true);
    perform set_config('request.jwt.claim.sub', a::text, true);
    perform set_config('request.headers', json_build_object('x-actor-user-id', s)::text, true);
    perform p16_test.assert('audit', 'header is IGNORED for non-service_role callers (cannot spoof actor)',
        current_actor_id() = a);
    perform set_config('request.jwt.claims', '', true);
    perform set_config('request.jwt.claim.sub', '', true);
    perform set_config('request.headers', '', true);

    -- 6.4 promotions ---------------------------------------------------------
    perform set_config('app.actor_user_id', s::text, true);
    insert into promotions(name, variant_id, discount_type, discount_value, starts_at, is_active)
        values ('P16 Promo', v, 'percentage', 10, now(), false) returning id into promo;
    select count(*) into n0 from audit_logs where entity_id = promo and action = 'promotion_created';
    perform p16_test.assert('audit', 'promotion create is audited', n0 = 1);

    update promotions set discount_value = 20 where id = promo;
    select * into row from audit_logs where entity_id = promo and action = 'promotion_updated';
    perform p16_test.assert('audit', 'promotion update is audited with before/after',
        (row.before_data ->> 'discount_value')::numeric = 10 and (row.after_data ->> 'discount_value')::numeric = 20
        and row.actor_user_id = s);

    select count(*) into n0 from audit_logs where entity_id = promo;
    update promotions set discount_value = 20 where id = promo;     -- no-op
    select count(*) into n1 from audit_logs where entity_id = promo;
    perform p16_test.assert('audit', 'no-op promotion update does not spam the log', n0 = n1);

    delete from promotions where id = promo;
    select * into row from audit_logs where entity_id = promo and action = 'promotion_deleted';
    perform p16_test.assert('audit', 'promotion DELETE is audited', row.id is not null and row.before_data ->> 'name' = 'P16 Promo');

    -- 6.5 feedback staff correction -----------------------------------------
    rid := p16_test.id('FEEDBACK_A');
    update feedback set staff_category = 'delivery', staff_sentiment = 'negative', staff_corrected = true where id = rid;
    select * into row from audit_logs where entity_id = rid and action = 'feedback_ai_tag_corrected';
    perform p16_test.assert('audit', 'feedback staff correction is audited', row.id is not null and row.actor_user_id = s);

    -- 6.6 support ticket changes ---------------------------------------------
    rid := p16_test.id('TICKET_A');
    update support_escalations set status = 'in_progress', priority = 'high' where id = rid;
    select * into row from audit_logs where entity_id = rid and action = 'support_ticket_updated';
    perform p16_test.assert('audit', 'support ticket status/priority change is audited',
        row.id is not null and row.after_data ->> 'status' = 'in_progress' and row.before_data ->> 'status' = 'open');

    -- 6.7 inventory correction ----------------------------------------------
    perform adjust_inventory(v, br, 5, 0, 'adjustment', 'p16 test', null, 'p16', '{}'::jsonb);
    select * into row from audit_logs where entity_type = 'branch_inventory' and action = 'inventory_adjustment'
        order by created_at desc limit 1;
    perform p16_test.assert('audit', 'inventory correction is audited with before/after stock',
        row.id is not null and (row.after_data ->> 'on_hand_quantity')::int = (row.before_data ->> 'on_hand_quantity')::int + 5,
        format('before=%s after=%s', row.before_data ->> 'on_hand_quantity', row.after_data ->> 'on_hand_quantity'));

    -- 6.8 reservations -------------------------------------------------------
    select count(*) into n0 from audit_logs where entity_type = 'reservations';
    res := create_reservation(a, v, br, 1, now() + interval '1 hour');
    select count(*) into n1 from audit_logs where entity_type = 'reservations';
    perform p16_test.assert('audit', 'reservation creation is audited', n1 > n0, format('%s -> %s rows', n0, n1));
    n0 := n1;
    perform release_reservation(res, 'released');
    select count(*) into n1 from audit_logs where entity_type = 'reservations';
    perform p16_test.assert('audit', 'reservation release is audited', n1 > n0, format('%s -> %s rows', n0, n1));

    -- 6.9 purchase -----------------------------------------------------------
    select count(*) into n0 from audit_logs where action = 'purchase_completed';
    perform execute_mock_purchase(a, v, br, 1, 'p16-audit-' || gen_random_uuid(), null);
    select count(*) into n1 from audit_logs where action = 'purchase_completed';
    perform p16_test.assert('audit', 'purchase completion is audited', n1 = n0 + 1, format('%s -> %s rows', n0, n1));

    perform set_config('app.actor_user_id', '', true);
end $$;


-- ===========================================================================
-- 7. audit_logs IS APPEND-ONLY, EVEN FOR THE OWNER AND service_role
-- ===========================================================================
do $$ begin perform p16_test.denied_as('audit', 'owner cannot UPDATE audit_logs', null, 'postgres',
    'update audit_logs set action = ''tampered'''); end $$;
do $$ begin perform p16_test.denied_as('audit', 'owner cannot DELETE audit_logs', null, 'postgres',
    'delete from audit_logs'); end $$;
do $$ begin perform p16_test.denied_as('audit', 'owner cannot TRUNCATE audit_logs', null, 'postgres',
    'truncate table audit_logs'); end $$;
do $$ begin perform p16_test.denied_as('audit', 'service_role cannot UPDATE audit_logs', null, 'service_role',
    'update audit_logs set action = ''tampered'''); end $$;
do $$ begin perform p16_test.denied_as('audit', 'service_role cannot DELETE audit_logs', null, 'service_role',
    'delete from audit_logs'); end $$;
do $$ begin perform p16_test.denied_as('audit', 'service_role cannot TRUNCATE audit_logs', null, 'service_role',
    'truncate table audit_logs'); end $$;

-- the ON DELETE SET NULL cascade (deleting a user) must still work and only blank the actor
do $$
declare
    u uuid := '00000000-0000-4000-8000-0000000000e9'; rid uuid; n_before bigint; n_after bigint; actor uuid;
begin
    insert into auth.users(id, email) values (u, 'p16-temp@example.test');
    perform set_config('app.actor_user_id', u::text, true);
    insert into promotions(name, variant_id, discount_type, discount_value, starts_at, is_active)
        values ('P16 Temp', p16_test.id('VAR'), 'percentage', 5, now(), false) returning id into rid;
    perform set_config('app.actor_user_id', '', true);

    select count(*) into n_before from audit_logs;
    delete from auth.users where id = u;
    select count(*) into n_after from audit_logs;
    select actor_user_id into actor from audit_logs where entity_id = rid and action = 'promotion_created';

    perform p16_test.assert('audit', 'deleting a user nulls the actor but keeps every audit row',
        actor is null and n_after >= n_before, format('rows %s -> %s, actor=%s', n_before, n_after, actor));
end $$;


-- ===========================================================================
-- REPORT
-- ===========================================================================
select area, count(*) filter (where ok) as passed, count(*) filter (where not ok) as failed
from p16_test.results group by area order by area;

select n, area, label, detail from p16_test.results where not ok order by n;

do $$
declare v_failed bigint; v_total bigint; v_list text;
begin
    select count(*) filter (where not ok), count(*) into v_failed, v_total from p16_test.results;
    if v_failed > 0 then
        select string_agg('[' || area || '] ' || label || ' -> ' || coalesce(detail, ''), E'\n' order by n)
          into v_list from p16_test.results where not ok;
        raise exception E'PHASE 16 SECURITY SUITE FAILED: % of % checks failed\n%', v_failed, v_total, v_list;
    end if;
    raise notice 'PHASE 16 SECURITY SUITE PASSED: all % checks OK (transaction will be rolled back)', v_total;
end $$;

rollback;
