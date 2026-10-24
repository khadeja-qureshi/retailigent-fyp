-- ============================================================================
-- PHASE 16: AUDIT LOGGING & SECURITY HARDENING  (plan name: 0010_audit_hardening)
--
-- 1. current_actor_id(): also honours the `x-actor-user-id` request header
--    when (and only when) the caller is service_role, and never returns an
--    id that is not a real profile (would break the audit_logs FK).
-- 2. audit_logs becomes append-only for EVERY role (incl. service_role/owner).
-- 3. audit_role_change() / audit_promotion_change() hardened; promotion
--    DELETEs are now audited; unattributed changes are labelled 'system'
--    instead of masquerading as 'staff'.
-- 4. Full grants review:
--      * EXECUTE on every function in `public` revoked from PUBLIC, anon and
--        authenticated (migrations 0001-0009 only revoked from PUBLIC, but
--        Supabase default privileges grant EXECUTE to anon/authenticated
--        directly, so those revokes were ineffective).
--      * service_role keeps EXECUTE on everything.
--      * authenticated keeps EXECUTE on an explicit read-only allowlist.
--      * default privileges changed so FUTURE functions are not client-callable.
--      * table privileges tightened: anon = SELECT on public catalog tables
--        only; authenticated = SELECT everywhere (RLS-filtered) and write
--        privileges ONLY where an RLS write policy exists; TRUNCATE /
--        REFERENCES / TRIGGER revoked from clients (RLS does not cover TRUNCATE).
-- 5. A self-check at the end aborts the migration if any non-allowlisted
--    function is still client-callable.
--
-- Safe to re-run (idempotent).
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. Actor attribution
-- ----------------------------------------------------------------------------
-- Resolution order:
--   a) SET LOCAL app.actor_user_id = '<profile uuid>'   (same transaction)
--   b) request header x-actor-user-id, ONLY when the JWT role is service_role
--      (PostgREST exposes headers via the request.headers setting; only the
--      backend holds the service key, so only the backend can assert this)
--   c) auth.uid()
create or replace function current_actor_id()
returns uuid
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    v_raw   text;
    v_actor uuid;
    v_role  text;
begin
    v_raw := nullif(current_setting('app.actor_user_id', true), '');

    if v_raw is null then
        begin
            v_role := coalesce(
                nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role',
                nullif(current_setting('request.jwt.claim.role', true), '')
            );

            if v_role = 'service_role' then
                v_raw := nullif(
                    (nullif(current_setting('request.headers', true), '')::jsonb)
                        ->> 'x-actor-user-id',
                    ''
                );
            end if;
        exception when others then
            v_raw := null;
        end;
    end if;

    if v_raw is not null then
        begin
            v_actor := v_raw::uuid;
        exception when invalid_text_representation then
            v_actor := null;
        end;

        if v_actor is not null
           and exists (select 1 from profiles where id = v_actor)
        then
            return v_actor;
        end if;
    end if;

    return auth.uid();
end;
$$;


-- ----------------------------------------------------------------------------
-- 2. audit_logs is append-only
-- ----------------------------------------------------------------------------
-- The only UPDATE allowed is the FK action `on delete set null` that clears
-- actor_user_id when a profile is deleted (nothing else may change).
create or replace function guard_audit_logs_immutable()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if TG_OP = 'UPDATE'
       and old.actor_user_id is not null
       and new.actor_user_id is null
       and (to_jsonb(new) - 'actor_user_id') = (to_jsonb(old) - 'actor_user_id')
    then
        return new;
    end if;

    raise exception 'audit_logs is append-only (% blocked)', TG_OP
        using errcode = '42501';
end;
$$;

drop trigger if exists trg_audit_logs_no_update_delete on audit_logs;
create trigger trg_audit_logs_no_update_delete
before update or delete on audit_logs
for each row execute function guard_audit_logs_immutable();

drop trigger if exists trg_audit_logs_no_truncate on audit_logs;
create trigger trg_audit_logs_no_truncate
before truncate on audit_logs
for each statement execute function guard_audit_logs_immutable();

create index if not exists idx_audit_logs_created
    on audit_logs(created_at desc);
create index if not exists idx_audit_logs_actor
    on audit_logs(actor_user_id, created_at desc);
create index if not exists idx_audit_logs_action
    on audit_logs(action, created_at desc);


-- ----------------------------------------------------------------------------
-- 3. Audit triggers (roles, promotions)
-- ----------------------------------------------------------------------------
create or replace function audit_role_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_actor uuid := current_actor_id();
begin
    insert into audit_logs(
        actor_user_id, actor_type, action, entity_type, entity_id,
        before_data, after_data, metadata
    )
    values (
        v_actor,
        case when v_actor is null then 'system' else 'staff' end,
        case when TG_OP = 'INSERT' then 'role_granted'
             when TG_OP = 'DELETE' then 'role_revoked'
             else 'role_updated' end,
        'user_roles',
        coalesce(new.id, old.id),
        case when TG_OP in ('UPDATE','DELETE')
             then jsonb_build_object('user_id', old.user_id, 'role', old.role)
             else null end,
        case when TG_OP in ('UPDATE','INSERT')
             then jsonb_build_object('user_id', new.user_id, 'role', new.role)
             else null end,
        jsonb_build_object('operation', TG_OP)
    );

    return coalesce(new, old);
end;
$$;

drop trigger if exists trg_role_audit on user_roles;
create trigger trg_role_audit
after insert or update or delete on user_roles
for each row execute function audit_role_change();


create or replace function audit_promotion_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_actor uuid := current_actor_id();
    v_before jsonb;
    v_after  jsonb;
begin
    -- No-op updates are not worth a log row.
    if TG_OP = 'UPDATE' and to_jsonb(new) = to_jsonb(old) then
        return new;
    end if;

    if TG_OP in ('UPDATE','DELETE') then
        v_before := jsonb_build_object(
            'name', old.name, 'product_id', old.product_id,
            'variant_id', old.variant_id, 'discount_type', old.discount_type,
            'discount_value', old.discount_value, 'is_active', old.is_active,
            'starts_at', old.starts_at, 'ends_at', old.ends_at,
            'priority', old.priority
        );
    end if;

    if TG_OP in ('INSERT','UPDATE') then
        v_after := jsonb_build_object(
            'name', new.name, 'product_id', new.product_id,
            'variant_id', new.variant_id, 'discount_type', new.discount_type,
            'discount_value', new.discount_value, 'is_active', new.is_active,
            'starts_at', new.starts_at, 'ends_at', new.ends_at,
            'priority', new.priority
        );
    end if;

    insert into audit_logs(
        actor_user_id, actor_type, action, entity_type, entity_id,
        before_data, after_data, metadata
    )
    values (
        v_actor,
        case when v_actor is null then 'system' else 'staff' end,
        case when TG_OP = 'INSERT' then 'promotion_created'
             when TG_OP = 'DELETE' then 'promotion_deleted'
             else 'promotion_updated' end,
        'promotions',
        coalesce(new.id, old.id),
        v_before,
        v_after,
        jsonb_build_object('operation', TG_OP)
    );

    return coalesce(new, old);
end;
$$;

drop trigger if exists trg_promotion_audit on promotions;
create trigger trg_promotion_audit
after insert or update or delete on promotions
for each row execute function audit_promotion_change();


-- ----------------------------------------------------------------------------
-- 4a. Function grants
-- ----------------------------------------------------------------------------
do $$
declare
    r record;
begin
    for r in
        select p.oid::regprocedure as sig
        from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public'
          and p.prokind in ('f', 'p')
          and not exists (
              select 1 from pg_depend d
              where d.objid = p.oid and d.deptype = 'e'   -- extension members
          )
    loop
        execute format(
            'revoke all on function %s from public, anon, authenticated', r.sig
        );
        execute format(
            'grant execute on function %s to service_role', r.sig
        );
    end loop;
end;
$$;

-- Explicit client-callable allowlist (authenticated only, all read-only):
--   is_staff()                       used inside RLS policies
--   get_stock_status(int)            pure label function
--   get_effective_variant_price(s)   read-only price lookup
grant execute on function is_staff() to authenticated;
grant execute on function get_stock_status(integer) to authenticated;
grant execute on function get_effective_variant_price(uuid) to authenticated;
grant execute on function get_effective_variant_prices(uuid[]) to authenticated;

-- Future functions created by the migration role are NOT client-callable.
do $$
begin
    alter default privileges for role postgres in schema public
        revoke execute on functions from public, anon, authenticated;
exception when others then
    raise notice 'default privileges (postgres) not changed: %', sqlerrm;
end;
$$;

do $$
begin
    alter default privileges in schema public
        revoke execute on functions from public, anon, authenticated;
exception when others then
    raise notice 'default privileges (current role) not changed: %', sqlerrm;
end;
$$;


-- ----------------------------------------------------------------------------
-- 4b. Table / view / sequence grants
-- ----------------------------------------------------------------------------
revoke all on all tables    in schema public from anon;
revoke all on all sequences in schema public from anon, authenticated;

-- RLS does not apply to TRUNCATE; REFERENCES/TRIGGER are never needed.
revoke truncate, references, trigger on all tables in schema public from authenticated;

-- Start authenticated from read-only; write privileges come back only where
-- an RLS write policy exists for authenticated/public.
revoke insert, update, delete on all tables in schema public from authenticated;

do $$
declare
    r record;
begin
    -- authenticated writes: exactly the commands that have a policy
    for r in
        select distinct tablename, upper(cmd) as cmd
        from pg_policies
        where schemaname = 'public'
          and cmd <> 'SELECT'
          and roles && array['authenticated', 'public']::name[]
    loop
        if r.cmd = 'ALL' then
            execute format(
                'grant insert, update, delete on public.%I to authenticated',
                r.tablename
            );
        else
            execute format(
                'grant %s on public.%I to authenticated', r.cmd, r.tablename
            );
        end if;
    end loop;

    -- anon: SELECT only on tables that have a policy for public/anon
    for r in
        select distinct tablename
        from pg_policies
        where schemaname = 'public'
          and cmd in ('SELECT', 'ALL')
          and roles && array['anon', 'public']::name[]
    loop
        execute format('grant select on public.%I to anon', r.tablename);
    end loop;
end;
$$;


-- ----------------------------------------------------------------------------
-- 5. Self-check: abort if anything unexpected is still client-callable
-- ----------------------------------------------------------------------------
do $$
declare
    v_bad text;
begin
    select string_agg(p.oid::regprocedure::text, ', ')
    into v_bad
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.prokind in ('f', 'p')
      and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')
      and (
            has_function_privilege('anon', p.oid, 'execute')
         or has_function_privilege('authenticated', p.oid, 'execute')
      )
      and p.oid::regprocedure::text not in (
            'is_staff()',
            'get_stock_status(integer)',
            'get_effective_variant_price(uuid)',
            'get_effective_variant_prices(uuid[])'
      );

    if v_bad is not null then
        raise exception 'Phase 16 self-check failed: client-callable functions remain: %', v_bad;
    end if;

    if exists (
        select 1
        from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public'
          and p.proname in ('is_staff','get_stock_status','get_effective_variant_price','get_effective_variant_prices')
          and has_function_privilege('anon', p.oid, 'execute')
    ) then
        raise exception 'Phase 16 self-check failed: anon can execute an allowlisted function';
    end if;
end;
$$;
