# Retailigent: Phase 16 Security Review

**Scope:** Postgres/Supabase privileges, RLS, audit logging, and the admin audit-log API/UI.
**Migration:** `supabase/migrations/20261026000000_phase16_audit_hardening.sql`
(the phase plan calls it `0010_audit_hardening.sql`; the repo uses timestamped names)
**Test suite:** `supabase/tests/phase16_rls_audit.sql` (580 checks)

## 1. Method

1. Rebuilt the full schema (all migrations through phase 15) in a local Postgres 16 that
   imitates Supabase: `anon` / `authenticated` / `service_role` roles, `auth.uid()`, and
   Supabase's default privileges (new tables and functions are granted to all three roles).
2. Enumerated every table, policy, function and grant from the system catalogs.
3. Wrote a scripted suite that switches to real `anon` / `authenticated` roles with
   forged JWT claims and attempts cross-customer reads/writes, privilege escalation and
   RPC abuse against **every** table and function in `public`.
4. Ran the suite **before** the migration (must fail) and **after** (must pass).

| Run | Result |
|---|---|
| Phase 15 schema (before) | 222 of 580 checks fail |
| Phase 15 + migration (after) | 580 of 580 pass |

> Not yet done: running the suite against the hosted Supabase project. See section 6.

## 2. Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| F1 | **High** | **Mutating `SECURITY DEFINER` functions were callable by any logged-in user (and by `anon`).** Earlier migrations ran `revoke ... from public`, but Supabase default privileges grant `EXECUTE` to `anon` and `authenticated` directly, so those revokes changed nothing. Affected: `adjust_inventory`, `execute_mock_purchase`, `create_reservation`, `convert_reservation_to_purchase`, `release_reservation`, `create_notification`, `upsert_customer_memory`, `get_customer_context_snapshot` (reads another customer's memory), `activate_due_promotions`, notification-delivery RPCs and others (117 function grants in total). These functions bypass RLS, so they can be invoked through `POST /rest/v1/rpc/<name>` with the public anon key and a customer JWT. | Fixed |
| F2 | Medium | `audit_logs` was not tamper-resistant: `service_role` and the table owner could UPDATE/DELETE/TRUNCATE it, and `authenticated`/`anon` held table-level write privileges (blocked only by RLS having no policy). | Fixed |
| F3 | Medium | `anon` and `authenticated` held `ALL` privileges (including `TRUNCATE`) on every table. RLS does not apply to `TRUNCATE`; PostgREST does not expose it, so this was reachable only over a direct DB connection. | Fixed |
| F4 | Low | Audit attribution: staff actions made through the backend (`service_role`) are logged with a null actor; role and promotion changes were labelled `staff` even when no actor was known; promotion DELETE was not audited. | Partly fixed (see 5.1) |
| F5 | Info | `is_staff()` accepts `manager`; the backend's `require_staff` accepts only `staff` and `admin`. A manager passes RLS but is refused by the API. | Open (decide intended behaviour) |

RLS itself is sound: all 46 tables have it enabled, every analytics view is
`security_invoker`, and zero cross-customer reads or writes were found on any table,
including `customer_memory` (staff cannot read it either).

## 3. What the migration changes

* **Function grants:** `EXECUTE` revoked from `PUBLIC`, `anon`, `authenticated` on every
  function in `public`; `service_role` keeps all. Client-callable allowlist (read-only,
  `authenticated` only): `is_staff()`, `get_stock_status(int)`,
  `get_effective_variant_price(uuid)`, `get_effective_variant_prices(uuid[])`.
* **Future functions** are not client-callable (default privileges changed).
* **Table grants:** `anon` gets `SELECT` only on the public catalog tables;
  `authenticated` gets `SELECT` everywhere (RLS-filtered) and write privileges only where an
  RLS write policy exists; `TRUNCATE`, `REFERENCES`, `TRIGGER` revoked.
* **`audit_logs` is append-only for every role**, including the owner and `service_role`
  (trigger). The one permitted UPDATE is the `ON DELETE SET NULL` cascade that blanks
  `actor_user_id` when a user is deleted.
* **Audit triggers:** `audit_role_change()` and `audit_promotion_change()` rewritten
  (promotion DELETE now audited, no-op updates skipped, unattributed changes labelled
  `system`). `audit_feedback_staff_correction()` already existed and is verified by the suite.
* **Self-check:** the migration aborts if any non-allowlisted function is still client-callable.
* **Indexes** on `audit_logs(created_at)`, `(actor_user_id, created_at)`, `(action, created_at)`.

## 4. Audit coverage (verified by the suite)

| Event | Audited as |
|---|---|
| Role granted / updated / revoked | `role_granted` / `role_updated` / `role_revoked` |
| Promotion created / updated / deleted | `promotion_created` / `promotion_updated` / `promotion_deleted` |
| Staff feedback re-classification | `feedback_ai_tag_corrected` |
| Support ticket status/priority/assignee | `support_ticket_updated` |
| Stock correction (adjustment, restock, damage, transfers) | `inventory_<movement>` with before/after stock |
| Reservation created / released / converted | rows with `entity_type = 'reservations'` |
| Purchase completed / failed | `purchase_completed` / `purchase_failed` |

Not audited by design: high-frequency `sale` / `reservation` stock movements (recorded in
`inventory_movements`) and price changes (recorded in `price_history`).

## 5. Residual risks and follow-ups

### 5.1 Actor attribution from the backend
The backend uses one shared `service_role` client, so database triggers cannot tell which
staff member acted. The database side is ready: `current_actor_id()` honours an
`x-actor-user-id` request header, **only** when the JWT role is `service_role`. The backend
does **not** send that header yet. Until it does, backend-driven staff actions show actor
"System / unattributed" (or a null actor) in the audit log. Sending the header per request
needs a request-scoped client (do not mutate the shared `httpx` client, or one request's actor
could leak into another's). Recommended for phase 17/18.

### 5.2 `app.actor_user_id` setting
`SET LOCAL app.actor_user_id` is honoured unconditionally (pre-existing behaviour). It can be
set by anyone with a direct SQL connection, which already implies full database access.
It is not reachable through the Supabase REST API.

### 5.3 Future tables
Supabase grants new tables to `anon`/`authenticated` by default. RLS keeps them safe, but a
new table without RLS would be exposed. The suite fails if any table is not classified, and
fails if RLS is off. Re-run it after every migration.

### 5.4 Not covered
Supabase Auth settings (email confirmation, rate limits, JWT expiry), storage policies beyond
`product-images`, backend rate limiting, secrets handling.

## 6. How to verify on the hosted project

**Before applying** (confirms F1 on the real project). Run in the SQL Editor:

```sql
select p.oid::regprocedure as function,
       has_function_privilege('anon', p.oid, 'execute')          as anon_can_run,
       has_function_privilege('authenticated', p.oid, 'execute') as customers_can_run
from pg_proc p
where p.pronamespace = 'public'::regnamespace
  and p.prokind in ('f','p')
  and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')
  and (has_function_privilege('anon', p.oid, 'execute')
    or has_function_privilege('authenticated', p.oid, 'execute'))
order by 1;
```
Rows with `customers_can_run = true` other than the four allowlisted functions are the exposure.

**Apply** (tell your groupmates first, it changes the shared database):
```bash
supabase db push
```
The migration prints nothing on success and raises `Phase 16 self-check failed` if anything
client-callable remains.

**Run the suite:** paste `supabase/tests/phase16_rls_audit.sql` into the SQL Editor and run it.
It runs in one transaction and always rolls back, so no fixtures persist. Expected final
message: `PHASE 16 SECURITY SUITE PASSED: all 580 checks OK`. (The count can differ slightly
if your hosted schema has extra tables or functions.) On failure it raises an error listing
every failed check.

**After applying, smoke-test the app:** log in as a customer and check cart, wishlist,
reservations, orders, notifications and chat; all go through the backend and should be unchanged.

## 7. Rollback

The migration only changes privileges, two functions and triggers. To undo the function
lock-down (not recommended):
```sql
grant execute on all functions in schema public to anon, authenticated;
```
and drop the append-only triggers:
```sql
drop trigger trg_audit_logs_no_update_delete on audit_logs;
drop trigger trg_audit_logs_no_truncate on audit_logs;
```
