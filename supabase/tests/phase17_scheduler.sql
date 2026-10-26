-- ============================================================================
-- PHASE 17: SCHEDULER / WORKER DATABASE TESTS
--
-- Proves the Phase 17 exit criteria at the database level:
--   * a future-dated promotion is activated by activate_due_promotions()
--     once its start time arrives (and only once)
--   * an expired reservation is released by release_expired_reservations()
--     and its stock is returned
-- and tests job heartbeats and notification retry / dead-letter handling.
--
-- HOW TO RUN: paste into the Supabase SQL Editor, or
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/phase17_scheduler.sql
-- Everything runs in ONE transaction that is ROLLED BACK at the end.
-- The last statement raises if any check failed.
-- ============================================================================
begin;

create schema p17_test;

create table p17_test.results (
    n serial primary key, area text not null, label text not null,
    ok boolean not null, detail text
);

create function p17_test.check(p_area text, p_label text, p_ok boolean, p_detail text default null)
returns void language sql as $$
    insert into p17_test.results(area, label, ok, detail)
    values (p_area, p_label, coalesce(p_ok, false), p_detail)
$$;

-- statement MUST be rejected with insufficient_privilege when run as a client role
create function p17_test.denied_as(p_label text, p_role text, p_uid uuid, p_sql text)
returns void language plpgsql as $$
declare v_ok boolean := false; v_msg text;
begin
    begin
        perform set_config('request.jwt.claim.sub', coalesce(p_uid::text, ''), true);
        perform set_config('request.jwt.claim.role', p_role, true);
        perform set_config('request.jwt.claims', json_build_object('sub', p_uid, 'role', p_role)::text, true);
        perform set_config('role', p_role, true);
        execute p_sql;
        v_msg := 'statement SUCCEEDED but must be denied';
    exception
        when insufficient_privilege then v_ok := true; v_msg := 'denied (42501)';
        when others then v_msg := 'unexpected error ' || sqlstate || ': ' || sqlerrm;
    end;
    execute 'reset role';
    perform p17_test.check('grants', p_label, v_ok, v_msg);
end $$;

create function p17_test.count_as(p_role text, p_uid uuid, p_sql text) returns bigint
language plpgsql as $$
declare v bigint;
begin
    begin
        perform set_config('request.jwt.claim.sub', coalesce(p_uid::text, ''), true);
        perform set_config('request.jwt.claim.role', p_role, true);
        perform set_config('request.jwt.claims', json_build_object('sub', p_uid, 'role', p_role)::text, true);
        perform set_config('role', p_role, true);
        execute p_sql into v;
    exception when others then
        execute 'reset role';
        return -1;
    end;
    execute 'reset role';
    return v;
end $$;


-- ---------------------------------------------------------------------------
-- Fixtures
-- ---------------------------------------------------------------------------
create table p17_test.ids (k text primary key, val uuid not null);

do $$
declare
    cust  uuid := '00000000-0000-4000-8000-0000000017a1';
    staff uuid := '00000000-0000-4000-8000-000000001751';
    v_prod uuid; v_var uuid; v_branch uuid;
begin
    insert into auth.users(id, email) values
        (cust, 'p17-customer@example.test'), (staff, 'p17-staff@example.test');
    insert into user_roles(user_id, role) values (staff, 'staff');

    insert into products(name, slug, base_price)
        values ('P17 Product', 'p17-product-' || gen_random_uuid(), 1000) returning id into v_prod;
    insert into product_variants(product_id, sku)
        values (v_prod, 'P17-' || gen_random_uuid()) returning id into v_var;
    insert into branches(name, city) values ('P17 Branch', 'Testville') returning id into v_branch;
    insert into branch_inventory(branch_id, variant_id, on_hand_quantity) values (v_branch, v_var, 20);

    insert into p17_test.ids values ('CUST', cust), ('STAFF', staff), ('VAR', v_var), ('BRANCH', v_branch);
end $$;


-- ===========================================================================
-- 1. EXIT CRITERION: a future-dated promotion activates on its own
-- ===========================================================================
do $$
declare
    v uuid := (select val from p17_test.ids where k = 'VAR');
    promo uuid; n_before bigint; n int; n_events bigint;
begin
    -- Isolate the scheduler function: the insert/update trigger would otherwise
    -- emit the event itself and hide a scheduler bug.
    alter table promotions disable trigger trg_promotion_event;

    insert into promotions(name, variant_id, discount_type, discount_value, starts_at, is_active)
        values ('P17 future sale', v, 'percentage', 10, now() + interval '1 hour', true)
        returning id into promo;

    select count(*) into n_events from retail_events
        where event_type = 'sale_started' and metadata ->> 'promotion_id' = promo::text;
    perform p17_test.check('promotions', 'future-dated promotion has NOT fired yet', n_events = 0);

    n := activate_due_promotions();
    select count(*) into n_events from retail_events
        where event_type = 'sale_started' and metadata ->> 'promotion_id' = promo::text;
    perform p17_test.check('promotions', 'scheduler tick before start time does nothing', n_events = 0,
        format('events=%s, returned=%s', n_events, n));

    -- time passes: the start time arrives
    update promotions set starts_at = now() - interval '1 minute' where id = promo;
    select count(*) into n_events from retail_events
        where event_type = 'sale_started' and metadata ->> 'promotion_id' = promo::text;
    perform p17_test.check('promotions', 'nothing fires by itself when the time arrives', n_events = 0);

    n := activate_due_promotions();
    select count(*) into n_events from retail_events
        where event_type = 'sale_started' and metadata ->> 'promotion_id' = promo::text;
    perform p17_test.check('promotions', 'next scheduler tick activates the promotion (sale_started event)',
        n_events = 1 and n >= 1, format('events=%s, returned=%s', n_events, n));

    n := activate_due_promotions();
    select count(*) into n_events from retail_events
        where event_type = 'sale_started' and metadata ->> 'promotion_id' = promo::text;
    perform p17_test.check('promotions', 'a second tick is idempotent (no duplicate event)',
        n_events = 1 and n = 0, format('events=%s, returned=%s', n_events, n));

    -- an inactive or expired promotion must never fire
    insert into promotions(name, variant_id, discount_type, discount_value, starts_at, ends_at, is_active)
        values ('P17 expired sale', v, 'percentage', 5, now() - interval '2 days', now() - interval '1 day', true)
        returning id into promo;
    n := activate_due_promotions();
    select count(*) into n_events from retail_events
        where event_type = 'sale_started' and metadata ->> 'promotion_id' = promo::text;
    perform p17_test.check('promotions', 'an already-ended promotion never fires', n_events = 0);

    insert into promotions(name, variant_id, discount_type, discount_value, starts_at, is_active)
        values ('P17 inactive sale', v, 'percentage', 5, now() - interval '1 hour', false)
        returning id into promo;
    n := activate_due_promotions();
    select count(*) into n_events from retail_events
        where event_type = 'sale_started' and metadata ->> 'promotion_id' = promo::text;
    perform p17_test.check('promotions', 'an inactive promotion never fires', n_events = 0);

    alter table promotions enable trigger trg_promotion_event;
end $$;


-- ===========================================================================
-- 2. EXIT CRITERION: an expired reservation is released within one tick
-- ===========================================================================
do $$
declare
    cust uuid := (select val from p17_test.ids where k = 'CUST');
    v uuid := (select val from p17_test.ids where k = 'VAR');
    br uuid := (select val from p17_test.ids where k = 'BRANCH');
    res_old uuid; res_live uuid;
    reserved_before int; reserved_after int; n int; st text;
begin
    res_old  := create_reservation(cust, v, br, 3, now() + interval '1 hour');
    res_live := create_reservation(cust, v, br, 2, now() + interval '1 hour');

    select reserved_quantity into reserved_before from branch_inventory where branch_id = br and variant_id = v;
    perform p17_test.check('reservations', 'two active reservations hold 5 units', reserved_before = 5,
        format('reserved=%s', reserved_before));

    -- time passes for one reservation
    update reservations set created_at = now() - interval '2 hours',
                            expires_at = now() - interval '1 minute'
    where id = res_old;

    n := release_expired_reservations();
    select status::text into st from reservations where id = res_old;
    perform p17_test.check('reservations', 'one tick releases the expired reservation',
        n = 1 and st = 'expired', format('released=%s status=%s', n, st));

    select status::text into st from reservations where id = res_live;
    perform p17_test.check('reservations', 'a still-valid reservation is untouched', st = 'active', 'status=' || st);

    select reserved_quantity into reserved_after from branch_inventory where branch_id = br and variant_id = v;
    perform p17_test.check('reservations', 'the expired reservation''s stock is returned',
        reserved_after = 2, format('reserved %s -> %s', reserved_before, reserved_after));

    n := release_expired_reservations();
    perform p17_test.check('reservations', 'a second tick is a no-op', n = 0, format('released=%s', n));

    perform p17_test.check('reservations', 'the release is audited',
        exists (select 1 from audit_logs where entity_type = 'reservations' and entity_id = res_old));
end $$;


-- ===========================================================================
-- 3. JOB HEARTBEATS
-- ===========================================================================
do $$
declare j job_runs;
begin
    perform record_job_run('p17_job', 60, true, null, 12, '{"released": 2}'::jsonb, now(), 1, 0, 0);
    select * into j from job_runs where job_name = 'p17_job';
    perform p17_test.check('jobs', 'first run creates the heartbeat row',
        j.run_count = 1 and j.last_status = 'ok' and j.last_success_at is not null and j.interval_seconds = 60
        and j.last_result ->> 'released' = '2');

    perform record_job_run('p17_job', 60, false, 'boom', 5, null, now(), 1, 1, 1);
    select * into j from job_runs where job_name = 'p17_job';
    perform p17_test.check('jobs', 'a failure is recorded without erasing the last success',
        j.last_status = 'failed' and j.last_error = 'boom' and j.last_success_at is not null
        and j.failure_count = 1 and j.consecutive_failures = 1 and j.run_count = 2);

    perform record_job_run('p17_job', 60, true, null, 7, null, now(), 10, 0, 0);
    select * into j from job_runs where job_name = 'p17_job';
    perform p17_test.check('jobs', 'counter deltas accumulate and recovery clears the failure streak',
        j.run_count = 12 and j.failure_count = 1 and j.consecutive_failures = 0 and j.last_error is null);

    perform record_job_run('p17_job', 60, false, repeat('x', 5000), 1, null, now(), 1, 1, 2);
    select * into j from job_runs where job_name = 'p17_job';
    perform p17_test.check('jobs', 'very long error text is truncated', length(j.last_error) <= 1000);
end $$;


-- ===========================================================================
-- 4. NOTIFICATION RETRY / DEAD-LETTER
-- ===========================================================================
do $$
declare
    cust uuid := (select val from p17_test.ids where k = 'CUST');
    nid uuid; did uuid; d notification_deliveries; claimed int; n int;
begin
    nid := create_notification(cust, 'general', 'p17 retry', 'body', '{}'::jsonb, false);
    select id into did from notification_deliveries where notification_id = nid and channel = 'in_app';

    -- 4.1 claim
    select count(*) into claimed from claim_notification_deliveries(100, 3, 30, 300) c where c.id = did;
    select * into d from notification_deliveries where id = did;
    perform p17_test.check('deliveries', 'claim moves a pending delivery to processing (attempt 1)',
        claimed = 1 and d.status = 'processing' and d.attempts = 1);

    -- 4.2 retryable failure keeps it in the queue
    perform fail_notification_delivery(did, 'smtp timeout', false, 3);
    select * into d from notification_deliveries where id = did;
    perform p17_test.check('deliveries', 'a retryable failure is NOT dead-lettered',
        d.status = 'failed' and d.dead_lettered_at is null and d.error_message = 'smtp timeout');

    -- 4.3 backoff: not claimable immediately
    select count(*) into claimed from claim_notification_deliveries(100, 3, 30, 300) c where c.id = did;
    perform p17_test.check('deliveries', 'backoff holds the retry back', claimed = 0, format('claimed=%s', claimed));

    -- 4.4 after backoff it is claimed again
    update notification_deliveries set last_attempt_at = now() - interval '1 hour' where id = did;
    select count(*) into claimed from claim_notification_deliveries(100, 3, 30, 300) c where c.id = did;
    select * into d from notification_deliveries where id = did;
    perform p17_test.check('deliveries', 'after the backoff the retry is claimed (attempt 2)',
        claimed = 1 and d.attempts = 2);

    -- 4.5 last allowed attempt fails -> dead letter
    perform fail_notification_delivery(did, 'still failing', false, 3);
    update notification_deliveries set last_attempt_at = now() - interval '1 hour' where id = did;
    select count(*) into claimed from claim_notification_deliveries(100, 3, 30, 300) c where c.id = did;   -- attempt 3
    perform fail_notification_delivery(did, 'third failure', false, 3);
    select * into d from notification_deliveries where id = did;
    perform p17_test.check('deliveries', 'the last allowed attempt failing dead-letters the delivery',
        d.attempts = 3 and d.dead_lettered_at is not null and d.status = 'failed');

    -- 4.6 dead letters are never claimed again
    update notification_deliveries set last_attempt_at = now() - interval '1 day' where id = did;
    select count(*) into claimed from claim_notification_deliveries(100, 3, 30, 300) c where c.id = did;
    perform p17_test.check('deliveries', 'a dead-lettered delivery is never claimed again', claimed = 0);

    -- 4.7 permanent error dead-letters on the first failure
    nid := create_notification(cust, 'general', 'p17 permanent', 'body', '{}'::jsonb, false);
    select id into did from notification_deliveries where notification_id = nid and channel = 'in_app';
    perform claim_notification_deliveries(100, 5, 30, 300);
    perform fail_notification_delivery(did, 'customer has no email address', true, 5);
    select * into d from notification_deliveries where id = did;
    perform p17_test.check('deliveries', 'a permanent error dead-letters immediately (attempt 1 of 5)',
        d.attempts = 1 and d.dead_lettered_at is not null);

    -- 4.8 a worker that crashed on its last attempt does not leave the row in limbo
    nid := create_notification(cust, 'general', 'p17 stuck', 'body', '{}'::jsonb, false);
    select id into did from notification_deliveries where notification_id = nid and channel = 'in_app';
    update notification_deliveries
       set status = 'processing', attempts = 3, last_attempt_at = now() - interval '1 hour' where id = did;
    perform claim_notification_deliveries(100, 3, 30, 300);
    select * into d from notification_deliveries where id = did;
    perform p17_test.check('deliveries', 'a stuck row with no attempts left is dead-lettered by the next claim',
        d.dead_lettered_at is not null and d.status = 'failed', format('status=%s', d.status));

    -- 4.9 a stuck row WITH attempts left is retried
    nid := create_notification(cust, 'general', 'p17 stuck2', 'body', '{}'::jsonb, false);
    select id into did from notification_deliveries where notification_id = nid and channel = 'in_app';
    update notification_deliveries
       set status = 'processing', attempts = 1, last_attempt_at = now() - interval '1 hour' where id = did;
    select count(*) into claimed from claim_notification_deliveries(100, 3, 30, 300) c where c.id = did;
    perform p17_test.check('deliveries', 'a stuck row with attempts left is reclaimed', claimed = 1);
end $$;

do $$
declare
    cust uuid := (select val from p17_test.ids where k = 'CUST');
    n1 uuid; n2 uuid; d1 uuid; d2 uuid; n int; st record; audits_before bigint; audits_after bigint;
begin
    delete from notification_deliveries where dead_lettered_at is not null;     -- start clean (rolled back)

    n1 := create_notification(cust, 'general', 'p17 dl 1', 'b', '{}'::jsonb, false);
    n2 := create_notification(cust, 'general', 'p17 dl 2', 'b', '{}'::jsonb, false);
    select id into d1 from notification_deliveries where notification_id = n1 and channel = 'in_app';
    select id into d2 from notification_deliveries where notification_id = n2 and channel = 'in_app';
    perform fail_notification_delivery(d1, 'x', true, 5);
    perform fail_notification_delivery(d2, 'y', true, 5);

    -- requeue only the selected delivery
    select count(*) into audits_before from audit_logs where action = 'notification_deliveries_requeued';
    n := requeue_dead_letter_deliveries(array[d1]);
    select * into st from notification_deliveries where id = d1;
    perform p17_test.check('deliveries', 'requeue resets the selected delivery',
        n = 1 and st.status = 'pending' and st.attempts = 0 and st.dead_lettered_at is null and st.error_message is null);
    select * into st from notification_deliveries where id = d2;
    perform p17_test.check('deliveries', 'requeue leaves other dead letters alone', st.dead_lettered_at is not null);

    select count(*) into audits_after from audit_logs where action = 'notification_deliveries_requeued';
    perform p17_test.check('deliveries', 'requeue is audited', audits_after = audits_before + 1);

    n := requeue_dead_letter_deliveries(null);
    perform p17_test.check('deliveries', 'requeue(null) recovers all remaining dead letters', n = 1);

    select count(*) into audits_before from audit_logs where action = 'notification_deliveries_requeued';
    n := requeue_dead_letter_deliveries(null);
    select count(*) into audits_after from audit_logs where action = 'notification_deliveries_requeued';
    perform p17_test.check('deliveries', 'requeue with nothing to do returns 0 and writes no audit row',
        n = 0 and audits_before = audits_after);
end $$;


-- ===========================================================================
-- 5. ACCESS CONTROL (Phase 16 policy applies to the new objects)
-- ===========================================================================
do $$
declare
    cust uuid := (select val from p17_test.ids where k = 'CUST');
    staff uuid := (select val from p17_test.ids where k = 'STAFF');
    total bigint; seen bigint;
    f text;
begin
    foreach f in array array[
        'record_job_run(''x'', 1, true, null, 1, null, now(), 1, 0, 0)',
        'claim_notification_deliveries(10, 5, 30, 300)',
        'fail_notification_delivery(gen_random_uuid(), ''x'', true, 5)',
        'requeue_dead_letter_deliveries(null)'
    ] loop
        perform p17_test.denied_as('customer cannot call ' || split_part(f, '(', 1), 'authenticated', cust, 'select ' || f);
        perform p17_test.denied_as('anon cannot call ' || split_part(f, '(', 1), 'anon', null, 'select ' || f);
        perform p17_test.denied_as('staff cannot call ' || split_part(f, '(', 1), 'authenticated', staff, 'select ' || f);
    end loop;

    perform p17_test.denied_as('anon cannot read job_runs', 'anon', null, 'select count(*) from job_runs');
    perform p17_test.denied_as('customer cannot write job_runs', 'authenticated', cust,
        'insert into job_runs(job_name, interval_seconds) values (''evil'', 1)');
    perform p17_test.denied_as('customer cannot update job_runs', 'authenticated', cust,
        'update job_runs set last_status = ''ok''');
    perform p17_test.denied_as('staff cannot write job_runs', 'authenticated', staff,
        'insert into job_runs(job_name, interval_seconds) values (''evil'', 1)');

    select count(*) into total from job_runs;
    seen := p17_test.count_as('authenticated', cust, 'select count(*) from job_runs');
    perform p17_test.check('grants', 'customer sees no job_runs rows', seen = 0, format('sees %s of %s', seen, total));
    seen := p17_test.count_as('authenticated', staff, 'select count(*) from job_runs');
    perform p17_test.check('grants', 'staff can read job_runs', seen = total and total > 0, format('sees %s of %s', seen, total));

    perform p17_test.check('grants', 'dead_lettered_at is not exposed to customers via notification_deliveries',
        p17_test.count_as('authenticated', cust, 'select count(*) from notification_deliveries') = 0);
end $$;


-- ===========================================================================
-- REPORT
-- ===========================================================================
select area, count(*) filter (where ok) as passed, count(*) filter (where not ok) as failed
from p17_test.results group by area order by area;

select n, area, label, detail from p17_test.results where not ok order by n;

do $$
declare v_failed bigint; v_total bigint; v_list text;
begin
    select count(*) filter (where not ok), count(*) into v_failed, v_total from p17_test.results;
    if v_failed > 0 then
        select string_agg('[' || area || '] ' || label || ' -> ' || coalesce(detail, ''), E'\n' order by n)
          into v_list from p17_test.results where not ok;
        raise exception E'PHASE 17 SCHEDULER TESTS FAILED: % of % checks failed\n%', v_failed, v_total, v_list;
    end if;
    raise notice 'PHASE 17 SCHEDULER TESTS PASSED: all % checks OK (transaction will be rolled back)', v_total;
end $$;

rollback;
