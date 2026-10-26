# Retailigent: Operations Guide (Phase 17)

How the backend's automatic work is scheduled, how to see that it is healthy, and what to do when it is not.

## 1. What runs automatically

One in-process scheduler (`backend/app/workers/scheduler.py`) starts with the API and runs four jobs
(registry: `backend/app/workers/jobs.py`). Nothing needs to be triggered by hand.

| Job | Every | What it does | Database function |
|---|---|---|---|
| `activate_promotions` | 60 s | Fires the `sale_started` event for promotions whose start time has arrived, which triggers price alerts and Smart Cart rules | `activate_due_promotions()` |
| `release_expired_reservations` | 30 s | Releases reservations past their expiry and returns the stock | `release_expired_reservations()` |
| `notification_delivery` | 5 s | Delivers queued in-app and email notifications; retries failures; dead-letters hopeless ones | `claim_notification_deliveries()` and friends |
| `smart_cart_auto_buy` | 2 s | Executes Auto Buy rules that have been triggered | (backend agent) |

An expired reservation is therefore released within one 30-second tick, and a promotion fires within one
60-second tick of its start time.

### Settings (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `SCHEDULER_ENABLED` | `true` | Master switch. `false` stops every job (tests, one-off scripts) |
| `PROMOTION_ACTIVATION_INTERVAL_SECONDS` | `60` | `0` disables the job |
| `RESERVATION_EXPIRY_INTERVAL_SECONDS` | `30` | `0` disables the job |
| `NOTIFICATION_WORKER_ENABLED` / `NOTIFICATION_WORKER_INTERVAL_SECONDS` | `true` / `5` | |
| `SMART_CART_WORKER_ENABLED` / `SMART_CART_WORKER_INTERVAL_SECONDS` | `true` / `2` | |
| `NOTIFICATION_MAX_ATTEMPTS` | `5` | Attempts before a delivery is dead-lettered |
| `NOTIFICATION_BACKOFF_SECONDS` | `30` | Base retry delay (doubles each attempt) |
| `JOB_HEARTBEAT_PERSIST_SECONDS` | `15` | How often a healthy job writes its heartbeat to the database |
| `LOG_FORMAT` / `LOG_LEVEL` | `json` / `INFO` | Use `text` for readable local logs |

### How the scheduler behaves

* Each job runs in its own task and its own worker thread. A slow or failing job never blocks the API or
  another job.
* A failing job **backs off**: its delay doubles per consecutive failure (capped at 5 minutes, never shorter
  than its own interval) and returns to normal after the first success.
* Every job is idempotent and uses `for update skip locked` in the database, so running two API instances is
  safe; it only duplicates cheap work.
* On startup every job runs once immediately, so a restart catches up on anything missed while it was down.
* Promotion activation used to run inside the Smart Cart loop every 2 seconds. It now runs once a minute as
  its own job, so Smart Cart reactions to a promotion can lag by up to a minute.

## 2. Checking health

### `GET /health/jobs` (public, for uptime monitors)

```json
{
  "status": "ok",
  "scheduler_started_at": "2026-10-27T08:00:00+00:00",
  "jobs": [
    {
      "name": "activate_promotions",
      "interval_seconds": 60.0,
      "last_started_at": "2026-10-27T08:05:00+00:00",
      "last_finished_at": "2026-10-27T08:05:00+00:00",
      "last_success_at": "2026-10-27T08:05:00+00:00",
      "last_status": "ok",
      "last_duration_ms": 41,
      "run_count": 6,
      "failure_count": 0,
      "consecutive_failures": 0,
      "stale": false
    }
  ]
}
```

* `status`: `ok`, `degraded` (some job is stale or has failed 3 times in a row) or `disabled` (scheduler off).
* `stale`: the job has not **succeeded** within `max(3 x interval, 30 s)`.
* The response carries times and counts only: no error text and no data. The endpoint always returns HTTP 200;
  alert on `status != "ok"`.
* It reports the instance that answers the request.

### `GET /api/v1/admin/jobs` (administrators only)

Everything above plus error text and last result, the heartbeats stored in the database (`job_runs`, the
cluster-wide view), and the notification backlog:

```json
"notification_backlog": { "pending": 0, "retrying": 1, "processing": 0, "dead_lettered": 2 },
"notification_dead_letters": [ { "id": "...", "channel": "email", "attempts": 1,
                                "error_message": "Customer has no email address" } ]
```

### SQL

```sql
select job_name, last_status, last_success_at, consecutive_failures, last_error
from job_runs order by job_name;
```

## 3. Notification delivery lifecycle

```
pending -> processing -> sent
              |
              +-> failed (retry after 30 s, 60 s, 120 s, 240 s) -> dead letter after attempt 5
              +-> failed permanently (no email address, deleted record) -> dead letter at once
```

* Retries happen in the database (`claim_notification_deliveries`), so they survive an API restart.
* A worker that crashes mid-delivery leaves the row in `processing`; it is reclaimed after 5 minutes, or
  dead-lettered if it has already used all its attempts.
* A **dead letter** is a delivery with `dead_lettered_at` set. It is never retried automatically.
* Email is opt-in per customer. A customer who has not opted in is skipped (counted as delivered), not
  dead-lettered.

### Recovering dead letters

1. Look at `notification_dead_letters` in `GET /api/v1/admin/jobs` and fix the cause (SMTP credentials, etc.).
2. Requeue (administrators only; audited as `notification_deliveries_requeued`):

```
POST /api/v1/admin/jobs/notification-dead-letters/requeue
{ "delivery_ids": ["<id>", "<id>"] }      // omit or null = every dead letter
```

or in SQL: `select requeue_dead_letter_deliveries(null);`

## 4. Logs

With `LOG_FORMAT=json` each line is one JSON object:

```json
{"ts":"2026-10-27T08:05:00.123+00:00","level":"INFO","logger":"retailigent.scheduler","message":"job_run",
 "event":"job_run","job":"release_expired_reservations","status":"ok","duration_ms":38,"result":{"released":2}}
```

* `event` values: `job_started`, `job_run`, `job_stopped`, `scheduler_started`, `scheduler_stopped`,
  `job_heartbeat_failed`, `notification_delivery_failed`.
* Idle ticks (nothing to do) log at `DEBUG` and are hidden at the default level. Ticks that did work log at
  `INFO`; failures log at `ERROR` with a traceback.
* Examples (with `jq`):

```bash
# every failed job run
... | jq 'select(.event=="job_run" and .status=="failed")'
# reservation releases
... | jq 'select(.job=="release_expired_reservations" and .result.released > 0)'
```

## 5. Runbook

| Symptom | Likely cause | Action |
|---|---|---|
| `/health/jobs` is `degraded` | A job is failing or stale | Open `GET /api/v1/admin/jobs` and read `last_error` |
| Every job fails together | Supabase unreachable or key wrong | Check `/health`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`; jobs recover by themselves |
| `status: disabled` | `SCHEDULER_ENABLED=false` or the API was started in a mode without lifespan | Set it to `true` and restart |
| Promotion did not fire | Promotion inactive, expired or has no matching variant; job off | `select * from job_runs where job_name='activate_promotions'`; check `is_active`, `starts_at`, `ends_at` |
| Stock stays reserved | Reservation not yet expired, or job off | `select id, status, expires_at from reservations where status='active' order by expires_at;` |
| Notifications pile up | Worker failing or SMTP down | Check backlog counts and `notification_delivery` job state; failures retry on their own |
| Many dead letters | Permanent cause (no address, bad SMTP credentials) | Fix, then requeue (section 3) |
| Need to pause one job | | Set its interval to `0` and restart |

## 6. Deploying

1. Apply the migration **first**: `supabase db push`
   (`20261027000000_phase17_scheduler_workers.sql`). It replaces `fail_notification_delivery` with a new
   signature. An old backend running against the new database cannot record a failed delivery; the row is
   simply reclaimed after 5 minutes, so the window is harmless but should be short.
2. Deploy the backend.
3. Confirm `GET /health/jobs` shows `ok` after a minute.
4. Run `supabase/tests/phase17_scheduler.sql` and `supabase/tests/phase16_rls_audit.sql` in the SQL Editor
   (both roll back; nothing persists).

## 7. Verifying the exit criteria on the real project

**A future-dated promotion activates on its own.** Pick any variant and start the promotion two minutes
from now:

```sql
insert into promotions(name, variant_id, discount_type, discount_value, starts_at, is_active)
select 'Ops test', id, 'percentage', 10, now() + interval '2 minutes', true
from product_variants limit 1
returning id;
```

Wait about three minutes without touching it, then:

```sql
select event_type, created_at from retail_events
where event_type = 'sale_started' and metadata ->> 'promotion_id' = '<promotion id>';
```

One row means the scheduler fired it. Clean up with `delete from promotions where id = '<promotion id>';`
(the event row stays; it is harmless).

**An expired reservation is released within one tick.** Use a real customer, variant and branch that has stock:

```sql
select create_reservation('<customer id>', '<variant id>', '<branch id>', 1, now() + interval '1 minute');
```

Wait about 1.5 minutes, then `select status from reservations where id = '<reservation id>';` should read
`expired`, and the branch's `reserved_quantity` should be back to what it was.

## 8. Known limits

* The scheduler lives inside the API process: if the API is down, no jobs run. When it comes back every job
  runs immediately. For heavier load, run jobs in a dedicated worker process (same code, no API routes) or
  move them to `pg_cron`.
* `GET /health/jobs` is per instance; use `job_runs` or the admin endpoint for the cluster-wide view.
* The existing `GET /health` still returns the raw database error text on failure. Consider trimming it
  before production.
